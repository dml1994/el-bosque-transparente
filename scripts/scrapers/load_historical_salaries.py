"""
Carga manual de retribuciones históricas de cargos electos de El Bosque.

TODO: Pendiente de rellenar con los datos de los acuerdos plenarios de El Bosque.

Fuentes a consultar:
  - Sede electrónica del Ayuntamiento de El Bosque: https://ayto-elbosque.es
  - Portal de transparencia municipal
  - Acuerdos plenarios de inicio de mandato (2015-2019, 2019-2023)

Los datos de 2023 y 2024 se cargan automáticamente con ispa_salaries.py.
Este script solo es necesario para años anteriores a 2023.

Uso:
    python scripts/scrapers/load_historical_salaries.py
"""

import sys
import logging

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger(__name__)


def run():
    log.warning(
        "load_historical_salaries.py no está configurado para El Bosque. "
        "Rellena los datos históricos a partir de los acuerdos plenarios del ayuntamiento."
    )
    return 0


if __name__ == "__main__":
    run()
