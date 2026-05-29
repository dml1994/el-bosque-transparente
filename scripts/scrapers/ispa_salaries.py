"""
Carga retribuciones de cargos electos de El Bosque desde los ficheros ISPA
(Información Salarial de Puestos de la Administración) del Ministerio de HACIENDA.

Fuente: ISPA 2024 (datos retribuciones año 2023)
  - retribuciones_alcaldes.xlsx
  - retribuciones_concejales.xlsx

El informe ISPA 2023 divide el año en dos períodos:
  - Período 1: 167 días (mandato 2019, hasta constitución nueva corporación ~17 junio 2023)
  - Período 2: 198 días (mandato 2023-2027, resto del año)

Se cargan ambas ediciones disponibles (ISPA 2024 → datos 2023, ISPA 2025 → datos 2024).

Uso:
    python scripts/scrapers/ispa_salaries.py          # descarga y carga
    python scripts/scrapers/ispa_salaries.py --year 2023
"""

import sys
import logging
import argparse
import io
import urllib.request
from typing import Optional, List

import psycopg2.extras

sys.path.insert(0, str(__import__("pathlib").Path(__file__).parent.parent))
from db import get_conn  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger(__name__)

MUNICIPALITY = "El Bosque"

ISPA_EDITIONS = {
    2023: {
        "base": "https://digital.gob.es/content/dam/portal-mtdfp/funcion-publica/dgfp/ispa/ispa2024/retrib_2023/",
        "source_url": "https://digital.gob.es/funcion-publica/dgfp/espacio-ispa/estadisticas/informac_estad_2023",
        "days_p1": 167,
        "days_p2": 198,
    },
    2024: {
        "base": "https://digital.gob.es/content/dam/portal-mtdfp/funcion-publica/dgfp/ispa/ispa2025/retrib_2024/",
        "source_url": "https://digital.gob.es/funcion-publica/dgfp/espacio-ispa/estadisticas/informac_estad_2024",
        "days_p1": 0,
        "days_p2": 366,
    },
}

# Nombres de cargos del mandato 2023-2027 (fuente: ayto-elbosque.es)
# Alcalde: Rubén Corrales Corbacho (PP, mayoría)
# PP concejales delegados: Alicia León Manzano, Lucía Rodríguez Román,
#   David España Ruiz, Antonio Ramírez Castro, Beatriz Salguero Pérez
# PSOE (4) y AxSí (1): oposición, sin dedicación retribuida presumiblemente
# Régimen de dedicación definitivo lo determina el propio ISPA al parsear.
COUNCIL_2023 = {
    "alcalde": "Rubén Corrales Corbacho",
    "1er_teniente": "Alicia León Manzano",
    "2a_teniente": "Lucía Rodríguez Román",
    "3er_teniente": "David España Ruiz",
    "4o_teniente": "Antonio Ramírez Castro",
    "concejal_delegado": [
        "Beatriz Salguero Pérez",
    ],
}

INSERT_SQL = """
INSERT INTO salaries (position, person_name, year, total)
VALUES (%(position)s, %(person_name)s, %(year)s, %(gross_annual)s)
"""


def download_xlsx(url: str) -> bytes:
    log.info("  Descargando %s", url)
    with urllib.request.urlopen(url, timeout=30) as r:
        return r.read()


def parse_el_bosque_rows(xlsx_bytes: bytes, sheet_name: str = "Hoja1") -> list:
    try:
        import openpyxl
    except ImportError:
        raise SystemExit("Instala openpyxl: pip install openpyxl")

    wb = openpyxl.load_workbook(io.BytesIO(xlsx_bytes), read_only=True, data_only=True)
    ws = wb[sheet_name]
    rows = []
    for row in ws.iter_rows(values_only=True):
        if any(isinstance(v, str) and MUNICIPALITY in v for v in row):
            rows.append(row)
    wb.close()
    return rows


def build_records_2023(alcalde_rows: list, concejal_rows: list, edition: dict) -> List[dict]:
    """Construye registros de salarios para el año 2023 (dos períodos)."""
    records = []
    src = edition["source_url"]
    doc = "ISPA 2024 — Retribuciones año 2023"
    days_p2 = edition["days_p2"]
    days_total = edition["days_p1"] + edition["days_p2"]

    # ─── Alcalde ─────────────────────────────────────────────────────────────
    p1_alcalde = [r for r in alcalde_rows if r[4] == 1]
    p2_alcalde = [r for r in alcalde_rows if r[4] == 2]
    if p1_alcalde and p2_alcalde:
        total_2023 = p1_alcalde[0][6] + p2_alcalde[0][6]
        records.append({
            "position": "Alcalde",
            "person_name": COUNCIL_2023["alcalde"],
            "year": 2023,
            "gross_annual": round(total_2023, 2),
            "source_url": src,
            "source_doc": doc,
        })
    elif p2_alcalde:
        ann = round(p2_alcalde[0][6] / days_p2 * days_total, 2)
        records.append({
            "position": "Alcalde",
            "person_name": COUNCIL_2023["alcalde"],
            "year": 2023,
            "gross_annual": ann,
            "source_url": src,
            "source_doc": doc,
        })

    # ─── Concejales ─────────────────────────────────────────────────────────
    p2_concejales = [r for r in concejal_rows if r[4] == 2]

    excl = sorted([r for r in p2_concejales if "Exclusiva" in str(r[5])], key=lambda r: -r[6])
    parc = [r for r in p2_concejales if "Parcial" in str(r[5])]
    sind = [r for r in p2_concejales if "Sin" in str(r[5])]

    # Período 1 concejales (para sumar al total anual 2023)
    p1_concejales = [r for r in concejal_rows if r[4] == 1]
    p1_excl = sorted([r for r in p1_concejales if "Exclusiva" in str(r[5])], key=lambda r: -r[6])

    # Con dedicación exclusiva — asignamos nombres del mandato 2023
    teniente_names = [
        ("1er Teniente de Alcalde", COUNCIL_2023["1er_teniente"]),
        ("2ª Teniente de Alcalde",  COUNCIL_2023["2a_teniente"]),
        ("3er Teniente de Alcalde", COUNCIL_2023["3er_teniente"]),
        ("4º Teniente de Alcalde",  COUNCIL_2023["4o_teniente"]),
    ]
    for i, row_p2 in enumerate(excl[:4]):
        pos, name = teniente_names[i]
        amount_p2 = row_p2[6]
        if i < len(p1_excl):
            # Mismo cargo en mandato anterior: sumar ambos períodos
            total_2023 = round(p1_excl[i][6] + amount_p2, 2)
        else:
            # Solo aparece en el nuevo mandato: anualizar P2
            total_2023 = round(amount_p2 / days_p2 * days_total, 2)
        records.append({
            "position": pos,
            "person_name": name,
            "year": 2023,
            "gross_annual": total_2023,
            "source_url": src,
            "source_doc": doc,
        })

    # Con dedicación parcial — concejales delegados
    deleg_names = COUNCIL_2023["concejal_delegado"]
    for i, row_p2 in enumerate(parc):
        # Parcial en período 1: en el mandato anterior eran "sin dedicación"
        # Se anualiza solo el período 2 más una estimación proporcional del P1
        ann = round(row_p2[6] / days_p2 * days_total, 2)
        records.append({
            "position": "Concejal Delegado/a (parcial)",
            "person_name": deleg_names[i] if i < len(deleg_names) else None,
            "year": 2023,
            "gross_annual": ann,
            "source_url": src,
            "source_doc": doc,
        })

    # Sin dedicación — solo dietas de asistencia a plenos
    if sind:
        # Agrupar por importe para registrar un representante por nivel
        niveles = {}
        for r in sind:
            niveles.setdefault(r[6], []).append(r)
        for amount, grupo in sorted(niveles.items(), reverse=True):
            ann = round(amount / days_p2 * days_total, 2)
            for j in range(len(grupo)):
                records.append({
                    "position": "Concejal/a (sin dedicación)",
                    "person_name": None,
                    "year": 2023,
                    "gross_annual": ann,
                    "source_url": src,
                    "source_doc": doc,
                })

    log.info("  %d registros generados para 2023", len(records))
    return records


def _row_ded_amount(row: tuple) -> tuple[str, float]:
    """Extrae (dedicación, importe) de una fila ISPA, soportando formato con y sin período."""
    # Formato 2023: (None, muni, prov, ccaa, periodo, dedicacion, importe, None)
    # Formato 2024: (None, muni, prov, ccaa, dedicacion, importe, None?)
    for i, v in enumerate(row):
        if isinstance(v, str) and any(k in v for k in ("Exclusiva", "Parcial", "Sin")):
            amount = row[i + 1]
            return v, float(amount) if amount is not None else 0.0
    return "Sin dedicación", 0.0


def build_records_simple(alcalde_rows: list, concejal_rows: list,
                         year: int, edition: dict) -> List[dict]:
    """Para años sin cambio de mandato (un solo período)."""
    records = []
    src = edition["source_url"]
    doc = f"ISPA — Retribuciones año {year}"

    for row in alcalde_rows:
        _, amount = _row_ded_amount(row)
        records.append({
            "position": "Alcalde",
            "person_name": COUNCIL_2023["alcalde"] if year >= 2023 else None,
            "year": year,
            "gross_annual": round(amount, 2),
            "source_url": src,
            "source_doc": doc,
        })

    excl_idx = 0
    parc_idx = 0
    teniente_names = [
        ("1er Teniente de Alcalde", COUNCIL_2023["1er_teniente"]),
        ("2ª Teniente de Alcalde",  COUNCIL_2023["2a_teniente"]),
        ("3er Teniente de Alcalde", COUNCIL_2023["3er_teniente"]),
        ("4º Teniente de Alcalde",  COUNCIL_2023["4o_teniente"]),
    ]
    deleg_names = COUNCIL_2023["concejal_delegado"]

    for row in concejal_rows:
        ded, amount = _row_ded_amount(row)
        if "Exclusiva" in ded:
            if excl_idx < len(teniente_names) and year >= 2023:
                pos, name = teniente_names[excl_idx]
            else:
                pos, name = "Teniente de Alcalde (exclusiva)", None
            excl_idx += 1
        elif "Parcial" in ded:
            if parc_idx < len(deleg_names) and year >= 2023:
                pos = "Concejal Delegado/a (parcial)"
                name = deleg_names[parc_idx]
            else:
                pos, name = "Concejal Delegado/a (parcial)", None
            parc_idx += 1
        else:
            pos, name = "Concejal/a (sin dedicación)", None

        records.append({
            "position": pos,
            "person_name": name,
            "year": year,
            "gross_annual": round(amount, 2),
            "source_url": src,
            "source_doc": doc,
        })

    log.info("  %d registros generados para %d", len(records), year)
    return records


def save_records(records: List[dict], year: int) -> int:
    if not records:
        return 0
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM salaries WHERE year = %s", (year,))
            deleted = cur.rowcount
            psycopg2.extras.execute_batch(cur, INSERT_SQL, records, page_size=100)
        conn.commit()
        if deleted:
            log.info("  Eliminados %d registros previos para %d", deleted, year)
        return len(records)
    finally:
        conn.close()


def run(years: Optional[List[int]] = None):
    target_years = years or list(ISPA_EDITIONS.keys())
    total = 0

    for year in target_years:
        if year not in ISPA_EDITIONS:
            log.warning("No hay edición ISPA configurada para %d, saltando", year)
            continue

        edition = ISPA_EDITIONS[year]
        base = edition["base"]
        log.info("Cargando ISPA año %d desde %s", year, base)

        try:
            alcalde_bytes = download_xlsx(base + "retribuciones_alcaldes.xlsx")
            concejal_bytes = download_xlsx(base + "retribuciones_concejales.xlsx")
        except Exception as e:
            log.error("Error descargando ficheros ISPA para %d: %s", year, e)
            continue

        alcalde_rows = parse_el_bosque_rows(alcalde_bytes)
        concejal_rows = parse_el_bosque_rows(concejal_bytes)
        log.info("  Alcalde: %d filas, Concejales: %d filas", len(alcalde_rows), len(concejal_rows))

        if year == 2023:
            records = build_records_2023(alcalde_rows, concejal_rows, edition)
        else:
            records = build_records_simple(alcalde_rows, concejal_rows, year, edition)

        saved = save_records(records, year)
        log.info("=== %d retribuciones cargadas para %d ===", saved, year)
        total += saved

    return total


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Carga retribuciones ISPA de El Bosque")
    parser.add_argument("--year", nargs="+", type=int, default=None,
                        help="Años a cargar (por defecto: todos disponibles)")
    args = parser.parse_args()
    run(args.year)
