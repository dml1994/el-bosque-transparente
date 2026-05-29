"""
Scraper de contratos del Ayuntamiento de El Bosque desde la PCSP.

Fuente: ZIPs de datos abiertos de la Plataforma de Contratación del Sector
Público (https://contrataciondelsectorpublico.gob.es).

Canales de sindicación:
  - sindicacion_643:  licitaciones en perfil de contratante
  - sindicacion_1044: licitaciones por agregación (CCAA)
  - sindicacion_1143: contratos menores

Estrategia por año:
  1. Intenta descargar el ZIP anual ({base}_{year}.zip).
  2. Si no existe (el servidor devuelve HTML en lugar de ZIP), busca ZIPs
     mensuales ({base}_{year}{mes:02d}.zip) — formato usado en 2025+.
  3. Itera los ficheros .atom dentro de cada ZIP sin extraerlos a disco.
  4. Filtra entradas por NIF del Ayuntamiento de Ubrique (P1101000F).
  5. Upserta los contratos en Neon PostgreSQL.
"""

import io
import zipfile
import logging
import sys
import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Optional, List, Dict
from xml.etree import ElementTree as ET

import requests
import psycopg2
import psycopg2.extras

# Ajusta sys.path para importar db.py desde scripts/
sys.path.insert(0, str(__import__("pathlib").Path(__file__).parent.parent))
from db import get_conn  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger(__name__)

# ─── Constantes ──────────────────────────────────────────────────────────────

EL_BOSQUE_NIF = "P1101100D"  # INE 11011 — verificar si hay contratos
EL_BOSQUE_DIR3 = "L01110110"  # TODO: verificar DIR3 en PCSP

# ZIPs de datos abiertos PCSP (actualizados diariamente)
BASE_SINDICACION = "https://contrataciondelsectorpublico.gob.es/sindicacion"

# Base de cada feed (sin sufijo _{periodo}.zip)
FEEDS = {
    "licitaciones": f"{BASE_SINDICACION}/sindicacion_643/licitacionesPerfilesContratanteCompleto3",
    "agregacion":   f"{BASE_SINDICACION}/sindicacion_1044/PlataformasAgregadasSinMenores",
    "menores":      f"{BASE_SINDICACION}/sindicacion_1143/contratosMenoresPerfilesContratantes",
}

FEED_STATUS = {
    "licitaciones": "awarded",
    "agregacion":   "awarded",
    "menores":      "awarded",
}

# Namespaces CODICE 2 usados en los ATOM de la PCSP
NS = {
    "atom":  "http://www.w3.org/2005/Atom",
    "cbc":   "urn:dgpe:names:draft:codice:schema:xsd:CommonBasicComponents-2",
    "cac":   "urn:dgpe:names:draft:codice:schema:xsd:CommonAggregateComponents-2",
    "cbc2":  "urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2",
}

# ─── Descarga ─────────────────────────────────────────────────────────────────

def url_is_zip(url: str, timeout: int = 30) -> bool:
    """True si la URL sirve un ZIP real.

    Usa Range: bytes=0-3 para obtener solo los primeros 4 bytes y comprobar
    el magic number del ZIP (PK). El servidor PCSP devuelve HTTP 200 + HTML
    para URLs inexistentes (HEAD y Content-Type no son fiables en este servidor).
    """
    try:
        r = requests.get(url, headers={"Range": "bytes=0-3"}, timeout=timeout, stream=False)
        return r.content[:2] == b"PK"
    except Exception:
        return False


def get_zip_urls(base_url: str, year: int) -> List[str]:
    """Devuelve las URLs de ZIPs disponibles para el año dado.

    Prueba primero el ZIP anual; si no existe (formato 2025+), busca
    los ZIPs mensuales del año.
    """
    annual = f"{base_url}_{year}.zip"
    if url_is_zip(annual):
        log.info("  ZIP anual encontrado: %s", annual)
        return [annual]

    log.info("  Sin ZIP anual para %d — buscando ZIPs mensuales...", year)
    today = datetime.date.today()
    max_month = today.month if year == today.year else 12

    monthly = []
    for month in range(1, max_month + 1):
        url = f"{base_url}_{year}{month:02d}.zip"
        if url_is_zip(url):
            monthly.append(url)

    if monthly:
        log.info("  %d ZIPs mensuales encontrados para %d", len(monthly), year)
    else:
        log.warning("  Sin ZIPs disponibles para %d en %s", year, base_url)

    return monthly


def download_zip(url: str, retries: int = 3) -> bytes:
    """Descarga un ZIP con reintentos para errores SSL intermitentes en Windows."""
    log.info("Descargando %s", url)
    last_err = None
    for attempt in range(1, retries + 1):
        try:
            # stream=False evita errores SSL de corte en mid-stream en Windows
            r = requests.get(url, timeout=300, stream=False)
            r.raise_for_status()
            data = r.content
            log.info("  Descarga completa: %.1f MB", len(data) / 1024 / 1024)
            return data
        except Exception as e:
            last_err = e
            log.warning("  Intento %d/%d fallido: %s", attempt, retries, e)
    raise last_err

# ─── Parser ATOM/CODICE ───────────────────────────────────────────────────────

def _text(el: Optional[ET.Element], *paths: str, ns=NS) -> Optional[str]:
    """Extrae texto del primer path que encuentre un elemento."""
    if el is None:
        return None
    for path in paths:
        found = el.find(path, ns)
        if found is not None and found.text:
            return found.text.strip()
    return None


def _is_el_bosque_entry(entry: ET.Element) -> bool:
    """True si el Ayuntamiento de Ubrique (NIF P1101000F) es el órgano contratante.

    El XML real de la PCSP usa LocatedContractingParty (no ContractingParty).
    Buscamos el NIF o DIR3 únicamente dentro de ese bloque por nombre local,
    para no confundir con entradas donde Ubrique aparece como municipio
    beneficiario de contratos de la Diputación u otras entidades.
    """
    cbc = "urn:dgpe:names:draft:codice:schema:xsd:CommonBasicComponents-2"
    IDENTIFIERS = (EL_BOSQUE_NIF, EL_BOSQUE_DIR3)

    NAME_TAGS = {"Name", "CityName", "RegistrationName"}

    for el in entry.iter():
        if el.tag.split("}")[-1] == "LocatedContractingParty":
            for child in el.iter():
                local = child.tag.split("}")[-1]
                text = child.text or ""
                if local == "ID" and any(ident in text for ident in IDENTIFIERS):
                    return True
                if local in NAME_TAGS and "El Bosque" in text:
                    return True
    return False


def _parse_awarded_to(entry: ET.Element) -> Optional[str]:
    """Extrae el nombre de la empresa adjudicataria desde TenderResult/WinningParty."""
    cbc = "urn:dgpe:names:draft:codice:schema:xsd:CommonBasicComponents-2"

    for el in entry.iter():
        if el.tag.split("}")[-1] == "WinningParty":
            for child in el.iter(f"{{{cbc}}}Name"):
                if child.text:
                    return child.text.strip()
    return None


def _parse_awarded_to_nif(entry: ET.Element) -> Optional[str]:
    """Extrae el NIF/CIF de la empresa adjudicataria desde TenderResult/WinningParty."""
    cbc = "urn:dgpe:names:draft:codice:schema:xsd:CommonBasicComponents-2"
    AYTO_NIFS = {EL_BOSQUE_NIF, EL_BOSQUE_DIR3}

    for el in entry.iter():
        if el.tag.split("}")[-1] == "WinningParty":
            for child in el.iter(f"{{{cbc}}}ID"):
                scheme = child.get("schemeName", "")
                if scheme == "NIF" and child.text and child.text.strip() not in AYTO_NIFS:
                    return child.text.strip()
    return None


def _parse_amount(entry: ET.Element) -> Optional[float]:
    """Extrae el importe del contrato."""
    tags = [
        "{urn:dgpe:names:draft:codice:schema:xsd:CommonBasicComponents-2}TaxExclusiveAmount",
        "{urn:dgpe:names:draft:codice:schema:xsd:CommonBasicComponents-2}EstimatedOverallContractAmount",
        "{urn:dgpe:names:draft:codice:schema:xsd:CommonBasicComponents-2}PayableAmount",
    ]
    for tag in tags:
        for el in entry.iter(tag):
            try:
                return float(el.text.replace(",", "."))
            except (ValueError, AttributeError):
                continue
    return None


def _parse_date(text: Optional[str]) -> Optional[datetime.date]:
    if not text:
        return None
    for fmt in ("%Y-%m-%dT%H:%M:%S", "%Y-%m-%d"):
        try:
            return datetime.datetime.strptime(text[:19], fmt).date()
        except ValueError:
            continue
    return None


def parse_entry(entry: ET.Element, feed_type: str) -> Optional[dict]:
    """Convierte un elemento <entry> ATOM en un dict listo para la BD."""
    atom_ns = "http://www.w3.org/2005/Atom"

    entry_id = _text(entry, f"{{{atom_ns}}}id")
    if not entry_id:
        return None

    title = _text(entry, f"{{{atom_ns}}}title")
    updated_raw = _text(entry, f"{{{atom_ns}}}updated")
    link_el = entry.find(f"{{{atom_ns}}}link")
    source_url = link_el.get("href") if link_el is not None else None

    # Datos CODICE
    cbc = "urn:dgpe:names:draft:codice:schema:xsd:CommonBasicComponents-2"
    contract_title = None
    for el in entry.iter(f"{{{cbc}}}ContractName"):
        contract_title = el.text
        break

    # Empresa adjudicataria
    awarded_to = _parse_awarded_to(entry)

    # Tipo de contrato — el elemento es TypeCode con listURI ContractCode
    # (hay otros TypeCode en el XML, p.ej. ContractingPartyTypeCode)
    contract_type = None
    for el in entry.iter(f"{{{cbc}}}TypeCode"):
        if "ContractCode" in el.get("listURI", ""):
            contract_type = el.text
            break

    # Fecha adjudicación
    award_date = None
    for el in entry.iter(f"{{{cbc}}}IssueDate"):
        award_date = _parse_date(el.text)
        break

    amount = _parse_amount(entry)
    published_date = _parse_date(updated_raw)

    return {
        "external_id":    entry_id,
        "title":          contract_title or title or "(Sin título)",
        "amount":         amount,
        "awarded_to":     awarded_to,
        "awarded_to_nif": _parse_awarded_to_nif(entry),
        "awarded_date":   award_date,
        "published_date": published_date,
        "contract_type":  contract_type,
        "status":         FEED_STATUS.get(feed_type, "published"),
        "source_url":     source_url,
    }

# ─── Procesado de ZIP ─────────────────────────────────────────────────────────

def process_zip(zip_bytes: bytes, feed_type: str) -> List[Dict]:
    """Itera los ficheros .atom en el ZIP y extrae contratos de El Bosque."""
    contracts = []
    with zipfile.ZipFile(io.BytesIO(zip_bytes)) as zf:
        atom_files = [n for n in zf.namelist() if n.endswith(".atom")]
        log.info("  %d ficheros .atom en el ZIP", len(atom_files))

        for atom_name in atom_files:
            with zf.open(atom_name) as f:
                try:
                    tree = ET.parse(f)
                except ET.ParseError as e:
                    log.warning("Error parseando %s: %s", atom_name, e)
                    continue

                root = tree.getroot()
                atom_ns = "http://www.w3.org/2005/Atom"
                for entry in root.findall(f"{{{atom_ns}}}entry"):
                    if _is_el_bosque_entry(entry):
                        parsed = parse_entry(entry, feed_type)
                        if parsed:
                            contracts.append(parsed)

    log.info("  %d contratos de El Bosque encontrados", len(contracts))
    return contracts

# ─── Persistencia ─────────────────────────────────────────────────────────────

UPSERT_SQL = """
INSERT INTO contracts (
    external_id, title, amount, awarded_to, awarded_to_nif, awarded_date,
    published_date, contract_type, status, source_url, updated_at
) VALUES (
    %(external_id)s, %(title)s, %(amount)s, %(awarded_to)s, %(awarded_to_nif)s, %(awarded_date)s,
    %(published_date)s, %(contract_type)s, %(status)s, %(source_url)s, NOW()
)
ON CONFLICT (external_id) DO UPDATE SET
    title          = EXCLUDED.title,
    amount         = EXCLUDED.amount,
    awarded_to     = EXCLUDED.awarded_to,
    awarded_to_nif = EXCLUDED.awarded_to_nif,
    awarded_date   = EXCLUDED.awarded_date,
    published_date = EXCLUDED.published_date,
    contract_type  = EXCLUDED.contract_type,
    status         = EXCLUDED.status,
    source_url     = EXCLUDED.source_url,
    updated_at     = NOW()
"""


def save_contracts(contracts: List[Dict]) -> int:
    if not contracts:
        return 0
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            psycopg2.extras.execute_batch(cur, UPSERT_SQL, contracts, page_size=100)
        conn.commit()
        return len(contracts)
    finally:
        conn.close()

# ─── Main ─────────────────────────────────────────────────────────────────────

def _process_feed_year(feed_type: str, base_url: str, year: int) -> int:
    """Descarga, parsea y guarda todos los ZIPs de un feed+año. Devuelve contratos guardados."""
    urls = get_zip_urls(base_url, year)
    saved = 0
    for url in urls:
        try:
            zip_bytes = download_zip(url)
            contracts = process_zip(zip_bytes, feed_type)
            saved += save_contracts(contracts)
            log.info("[%s/%d] %s → %d contratos guardados", feed_type, year, url, saved)
        except Exception as e:
            log.error("Error procesando %s: %s", url, e, exc_info=True)
    return saved


def run(years: Optional[List[int]] = None, feeds: Optional[List[str]] = None) -> int:
    if years is None:
        years = [datetime.date.today().year]

    active_feeds = {k: v for k, v in FEEDS.items() if feeds is None or k in feeds}

    tasks = [
        (feed_type, base_url, year)
        for year in years
        for feed_type, base_url in active_feeds.items()
    ]

    total = 0
    max_workers = min(len(tasks), 6)
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {
            executor.submit(_process_feed_year, ft, url, yr): (ft, yr)
            for ft, url, yr in tasks
        }
        for future in as_completed(futures):
            feed_type, year = futures[future]
            try:
                total += future.result()
            except Exception as e:
                log.error("Error en feed=%s año=%d: %s", feed_type, year, e, exc_info=True)

    log.info("=== Total: %d contratos upsertados ===", total)
    return total


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Scraper contratos PCSP — El Bosque")
    parser.add_argument("--years", nargs="+", type=int, default=None,
                        help="Años a procesar (por defecto: año actual)")
    parser.add_argument("--feeds", nargs="+", choices=list(FEEDS.keys()), default=None,
                        help="Feeds a procesar (por defecto: todos)")
    parser.add_argument("--backfill", action="store_true",
                        help="Carga histórica: procesa 2018 hasta el año actual")
    args = parser.parse_args()

    if args.backfill:
        current = datetime.date.today().year
        years = list(range(2018, current + 1))
    else:
        years = args.years

    run(years, feeds=args.feeds)
