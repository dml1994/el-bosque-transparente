"""
Scraper de presupuestos municipales de Ubrique desde Gobierto/Hacienda.

Fuente: bubbles.json publicado en S3 por Gobierto, alimentado con los datos
que los ayuntamientos remiten al Ministerio de Hacienda (CONPREL).

Cubre los años 2010–año actual con clasificación funcional (gastos) y
económica (ingresos), a nivel de categoría agregada.

Uso:
    python scripts/scrapers/gobierto_budget.py          # todos los años
    python scripts/scrapers/gobierto_budget.py --years 2023 2024
"""

import sys
import logging
import argparse
import datetime
from typing import Optional, List

import requests
import psycopg2.extras

sys.path.insert(0, str(__import__("pathlib").Path(__file__).parent.parent))
from db import get_conn  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger(__name__)

INE_CODE   = "11038"   # Ubrique (Cádiz)
BUBBLES_URL = (
    f"https://gobierto-populate-production.s3.eu-west-1.amazonaws.com"
    f"/gobierto_budgets/{INE_CODE}/data/bubbles.json"
)

SECTION_LABELS = {
    "expense": "Gastos",
    "income":  "Ingresos",
}
PROGRAM_LABELS = {
    "functional": "Funcional",
    "economic":   "Económica",
}

UPSERT_SQL = """
INSERT INTO budget_lines (year, section, program, category, description, planned_amount)
VALUES (%(year)s, %(section)s, %(program)s, %(category)s, %(description)s, %(planned_amount)s)
ON CONFLICT (year, section, program, category) DO UPDATE SET
    description    = EXCLUDED.description,
    planned_amount = EXCLUDED.planned_amount
"""


def fetch_bubbles() -> list:
    log.info("Descargando datos de Gobierto: %s", BUBBLES_URL)
    r = requests.get(BUBBLES_URL, timeout=30)
    r.raise_for_status()
    data = r.json()
    log.info("  %d categorías descargadas", len(data))
    return data


def build_records(data: list, years: Optional[List[int]] = None) -> List[dict]:
    records = []
    source_url = f"https://presupuestos.gobierto.es/municipios/el-bosque"  # TODO: verificar municipio en Gobierto

    for item in data:
        category     = item.get("id", "")
        description  = item.get("level_2_es") or item.get("level_2_ca") or category
        section      = SECTION_LABELS.get(item.get("budget_category", ""), item.get("budget_category", ""))
        program      = PROGRAM_LABELS.get(item.get("area_name", ""), item.get("area_name", ""))
        values       = item.get("values", {})

        for year_str, amount in values.items():
            year = int(year_str)
            if years and year not in years:
                continue
            if amount is None:
                continue
            records.append({
                "year":           year,
                "section":        section,
                "program":        program,
                "category":       category,
                "description":    description,
                "planned_amount": float(amount),
                "source_url":     f"{source_url}/{year}",
            })

    log.info("  %d registros generados", len(records))
    return records


def save_records(records: List[dict]) -> int:
    if not records:
        return 0
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            psycopg2.extras.execute_batch(cur, UPSERT_SQL, records, page_size=200)
        conn.commit()
        return len(records)
    finally:
        conn.close()


def run(years: Optional[List[int]] = None):
    data = fetch_bubbles()
    records = build_records(data, years)
    saved = save_records(records)
    log.info("=== %d partidas presupuestarias upsertadas ===", saved)
    return saved


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Scraper presupuestos Ubrique desde Gobierto")
    parser.add_argument("--years", nargs="+", type=int, default=None,
                        help="Años a cargar (por defecto: todos disponibles)")
    args = parser.parse_args()
    run(args.years)
