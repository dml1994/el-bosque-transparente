"""
Scraper de contratos del Ayuntamiento de El Bosque desde la plataforma
de la Diputación de Cádiz (www3.dipucadiz.es).

El Bosque publica su perfil de contratante en la plataforma provincial
(org=1343) en lugar de en el PCSP nacional. Este scraper extrae todas
las secciones: licitaciones, adjudicaciones provisionales, adjudicaciones
definitivas e histórico.

Uso:
    python scripts/scrapers/dipucadiz_contracts.py
    python scripts/scrapers/dipucadiz_contracts.py --dry-run
"""

import sys
import re
import logging
import argparse
import datetime
from typing import Optional
from urllib.parse import urljoin

import html as html_mod
import requests
import psycopg2.extras
from bs4 import BeautifulSoup

sys.path.insert(0, str(__import__("pathlib").Path(__file__).parent.parent))
from db import get_conn  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger(__name__)

BASE_URL   = "https://www3.dipucadiz.es"
ORG_ID     = "1343"   # Ayuntamiento de El Bosque
PAGE_SIZE  = 50

HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; UbriqueTransparente/1.0)",
    "Accept-Language": "es-ES,es;q=0.9",
}

# Secciones y su mapeo a status en BD
SECTIONS = {
    "licitacionN":    "published",
    "adjProvisionalN": "in_progress",
    "adjDefinitivaN":  "awarded",
}

UPSERT_SQL = """
INSERT INTO contracts (
    external_id, title, amount, awarded_to, awarded_to_nif,
    awarded_date, published_date, contract_type, status, source_url, updated_at
) VALUES (
    %(external_id)s, %(title)s, %(amount)s, %(awarded_to)s, %(awarded_to_nif)s,
    %(awarded_date)s, %(published_date)s, %(contract_type)s, %(status)s, %(source_url)s, NOW()
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


def get(url: str, **kwargs) -> requests.Response:
    r = requests.get(url, headers=HEADERS, timeout=30, **kwargs)
    r.raise_for_status()
    # Forzar UTF-8 — el servidor puede declarar latin-1 pero enviar UTF-8
    if r.encoding and r.encoding.lower() in ("iso-8859-1", "latin-1", "windows-1252"):
        r.encoding = r.apparent_encoding
    return r


def clean(text: Optional[str]) -> Optional[str]:
    if not text:
        return None
    return html_mod.unescape(text).strip() or None


def parse_date(text: Optional[str]) -> Optional[datetime.date]:
    if not text:
        return None
    text = text.strip()
    for fmt in ("%d-%m-%Y %H:%M:%S", "%d-%m-%Y", "%Y-%m-%d"):
        try:
            return datetime.datetime.strptime(text[:len(fmt)], fmt).date()
        except ValueError:
            continue
    return None


def parse_amount(text: Optional[str]) -> Optional[float]:
    if not text:
        return None
    cleaned = re.sub(r"[€\s]", "", text.replace(".", "").replace(",", "."))
    try:
        return float(cleaned)
    except ValueError:
        return None


def get_contract_ids(section: str) -> list[str]:
    """Pagina la lista y devuelve todos los IDs de contratos de una sección."""
    ids = []
    offset = 0
    while True:
        url = f"{BASE_URL}/perfiles/{section}/list"
        params = {"org": ORG_ID, "max": PAGE_SIZE, "offset": offset}
        try:
            resp = get(url, params=params)
        except Exception as e:
            log.warning("Error obteniendo lista %s offset=%d: %s", section, offset, e)
            break

        soup = BeautifulSoup(resp.text, "lxml")

        # Buscar enlaces de detalle: /perfiles/{section}/show/{id}
        pattern = re.compile(rf"/perfiles/{section}/show/(\d+)")
        found = []
        for a in soup.find_all("a", href=pattern):
            m = pattern.search(a["href"])
            if m:
                found.append(m.group(1))

        # Deduplicar manteniendo orden
        for cid in found:
            if cid not in ids:
                ids.append(cid)

        log.info("  [%s] offset=%d → %d IDs encontrados (total acum. %d)",
                 section, offset, len(found), len(ids))

        # Si devuelve menos de PAGE_SIZE, hemos terminado
        if len(found) < PAGE_SIZE:
            break
        offset += PAGE_SIZE

    return ids


def scrape_detail(section: str, contract_id: str, status: str) -> Optional[dict]:
    """Extrae los campos de la página de detalle de un contrato."""
    url = f"{BASE_URL}/perfiles/{section}/show/{contract_id}"
    try:
        resp = get(url)
    except Exception as e:
        log.warning("Error en detalle %s/%s: %s", section, contract_id, e)
        return None

    soup = BeautifulSoup(resp.text, "lxml")

    def cell(label: str) -> Optional[str]:
        """Busca una celda de tabla por su etiqueta y devuelve el valor limpio."""
        for th in soup.find_all(["th", "td", "label", "dt"]):
            if label.lower() in th.get_text().lower():
                nxt = th.find_next_sibling(["td", "dd"])
                if nxt:
                    return clean(nxt.get_text(strip=True))
                row = th.find_parent("tr")
                if row:
                    cells = row.find_all("td")
                    if len(cells) >= 2:
                        return clean(cells[-1].get_text(strip=True))
        return None

    # Título: buscar el campo "objeto" en la tabla antes que el h1 de la página
    title = (
        cell("objeto del contrato") or
        cell("objeto") or
        cell("descripci") or
        cell("título")
    )
    if not title:
        # Fallback: primer h2/h3 que no sea el nombre de la sección
        for tag in ["h2", "h3"]:
            h = soup.find(tag)
            if h:
                t = clean(h.get_text())
                if t and len(t) > 10 and "licitaci" not in t.lower() and "adjudicaci" not in t.lower():
                    title = t
                    break
    if not title:
        title = "(Sin título)"

    # Expediente como external_id
    expediente = cell("expediente") or cell("número")
    external_id = f"dipucadiz_{contract_id}"
    if expediente:
        external_id = f"dipucadiz_{expediente.replace('/', '_').replace(' ', '')}"

    record = {
        "external_id":    external_id,
        "title":          (title or "(Sin título)")[:500],
        "amount":         parse_amount(
                              cell("importe de licitación") or
                              cell("importe") or cell("presupuesto") or cell("valor")
                          ),
        "awarded_to":     cell("adjudicatari") or cell("empresa") or cell("contratista"),
        "awarded_to_nif": cell("nif") or cell("cif"),
        "published_date": parse_date(cell("fecha de publicaci") or cell("publicaci") or cell("fecha")),
        "awarded_date":   parse_date(cell("fecha de adjudicaci") or cell("adjudicaci") or cell("formalizaci")),
        "contract_type":  cell("tipo de contrato") or cell("tipo"),
        "status":         status,
        "source_url":     url,
    }

    return record


def save(records: list, dry_run: bool = False) -> int:
    if not records:
        return 0
    if dry_run:
        for r in records[:3]:
            log.info("  [DRY] %s | %s | %s€", r["external_id"], r["title"][:50], r["amount"])
        return len(records)

    conn = get_conn()
    try:
        with conn.cursor() as cur:
            psycopg2.extras.execute_batch(cur, UPSERT_SQL, records, page_size=50)
        conn.commit()
        return len(records)
    finally:
        conn.close()


def run(dry_run: bool = False) -> int:
    total = 0
    for section, status in SECTIONS.items():
        log.info("=== Sección: %s ===", section)
        ids = get_contract_ids(section)
        log.info("  %d contratos en total", len(ids))

        records = []
        for i, cid in enumerate(ids, 1):
            record = scrape_detail(section, cid, status)
            if record:
                records.append(record)
            if i % 10 == 0:
                log.info("  Procesados %d/%d...", i, len(ids))

        saved = save(records, dry_run)
        log.info("  %d contratos guardados de %s", saved, section)
        total += saved

    log.info("=== Total: %d contratos upsertados ===", total)
    return total


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Scraper contratos Diputación de Cádiz — El Bosque")
    parser.add_argument("--dry-run", action="store_true",
                        help="Muestra los datos sin guardar en BD")
    args = parser.parse_args()
    run(dry_run=args.dry_run)
