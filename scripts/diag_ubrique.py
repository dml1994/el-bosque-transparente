"""Diagnóstico de cobertura de ZIPs de la PCSP por año.

Fase 1 (rápida, sin descargas): descubre si existen múltiples ZIPs por año
        probando variantes de URL (_N, _0N, _año_N …).
Fase 2 (lenta, opcional): descarga un ZIP concreto y muestra su estructura interna.

Modos de uso:
  python scripts/diag_ubrique.py                        # descubre URLs de todos los años
  python scripts/diag_ubrique.py --year 2022            # descubre URLs de un año
  python scripts/diag_ubrique.py --inspect URL          # descarga y muestra estructura interna
  python scripts/diag_ubrique.py --full 2025            # análisis completo Ubrique
"""
import io, os, sys, tempfile, collections, datetime, zipfile, argparse, requests
from xml.etree import ElementTree as ET

sys.stdout.reconfigure(encoding="utf-8")

BASE = "https://contrataciondelsectorpublico.gob.es/sindicacion"
FEED_BASES = {
    "licitaciones": f"{BASE}/sindicacion_643/licitacionesPerfilesContratanteCompleto3",
    "menores":      f"{BASE}/sindicacion_1143/contratosMenoresPerfilesContratantes",
}
ATOM_NS      = "http://www.w3.org/2005/Atom"
CBC          = "urn:dgpe:names:draft:codice:schema:xsd:CommonBasicComponents-2"
EL_BOSQUE_NIF  = "P1101000F"
EL_BOSQUE_DIR3 = "L01110100"
IDENTIFIERS  = (EL_BOSQUE_NIF, EL_BOSQUE_DIR3)
CURRENT_YEAR = datetime.date.today().year


# ── Comprobación de existencia de URL (sin descargar) ─────────────────────────

def url_exists(url: str, timeout: int = 15) -> bool:
    """True si la URL sirve un ZIP real (Content-Type: application/zip).
    El servidor devuelve 200+HTML para URLs inexistentes, asi que
    no basta comprobar el status code."""
    try:
        r = requests.get(url, stream=True, timeout=timeout, allow_redirects=True)
        is_zip = "zip" in r.headers.get("Content-Type", "").lower()
        r.close()
        return is_zip
    except Exception:
        return False


def discover_zip_urls(feed_base: str, year: int) -> list:
    """Devuelve todas las URLs de ZIP que existen para ese feed y año.

    Prueba:
      {base}_{year}.zip          ← URL canónica actual
      {base}_{year}_1.zip …      ← partes numeradas
      {base}_{year}_01.zip …     ← partes con cero inicial
    """
    found = []

    # URL canónica
    canonical = f"{feed_base}_{year}.zip"
    if url_exists(canonical):
        found.append(canonical)

    # Variantes numeradas (hasta 2 misses consecutivos)
    for fmt in ("{base}_{year}_{n}.zip", "{base}_{year}_{n:02d}.zip"):
        misses = 0
        for n in range(1, 20):
            url = fmt.format(base=feed_base, year=year, n=n)
            if url_exists(url):
                if url not in found:
                    found.append(url)
                misses = 0
            else:
                misses += 1
                if misses >= 2:
                    break

    return found


# ── Descarga en streaming a disco ─────────────────────────────────────────────

def stream_to_tempfile(url: str) -> tuple:
    """Descarga url en streaming a un fichero temporal. Devuelve (path, bytes)."""
    r = requests.get(url, stream=True, timeout=600)
    r.raise_for_status()
    fd, path = tempfile.mkstemp(suffix=".zip")
    total = 0
    last_report = 0
    try:
        with os.fdopen(fd, "wb") as f:
            for chunk in r.iter_content(chunk_size=4 * 1024 * 1024):
                f.write(chunk)
                total += len(chunk)
                if total - last_report >= 50 * 1024 * 1024:
                    print(f"    … {total/1024/1024:.0f} MB descargados")
                    last_report = total
        print(f"    Descarga completa: {total/1024/1024:.1f} MB")
        return path, total
    except Exception:
        os.unlink(path)
        raise


# ── Estructura interna del ZIP ────────────────────────────────────────────────

def summarize_names(names: list, indent: str = "  ") -> None:
    by_ext: collections.Counter = collections.Counter()
    for n in names:
        ext = n.rsplit(".", 1)[-1].lower() if "." in n else "(sin ext)"
        by_ext[ext] += 1
    for ext, count in sorted(by_ext.items(), key=lambda x: -x[1]):
        print(f"{indent}.{ext}: {count}")
    print(f"{indent}Muestra (máx 10):")
    for n in names[:10]:
        print(f"{indent}  {n}")
    if len(names) > 10:
        print(f"{indent}  … y {len(names) - 10} más")


def inspect_zip_file(path: str) -> None:
    with zipfile.ZipFile(path) as zf:
        names = zf.namelist()
        print(f"  {len(names)} ficheros en el ZIP:")
        summarize_names(names)

        nested = [n for n in names if n.lower().endswith(".zip")]
        if nested:
            print(f"\n  ⚠ {len(nested)} ZIP(s) anidado(s):")
            for nz in nested[:3]:
                print(f"\n    ZIP anidado: {nz}")
                with zf.open(nz) as f:
                    inner_bytes = f.read()
                try:
                    with zipfile.ZipFile(io.BytesIO(inner_bytes)) as izf:
                        inner_names = izf.namelist()
                    summarize_names(inner_names, indent="      ")
                except Exception as e:
                    print(f"      Error al abrir: {e}")
            if len(nested) > 3:
                print(f"    … y {len(nested)-3} más")
        else:
            print("  Sin ZIPs anidados.")


# ── Análisis Ubrique ──────────────────────────────────────────────────────────

def is_ubrique_entry(entry: ET.Element) -> bool:
    for el in entry.iter():
        if el.tag.split("}")[-1] == "LocatedContractingParty":
            for child in el.iter(f"{{{CBC}}}ID"):
                if child.text and any(i in child.text for i in IDENTIFIERS):
                    return True
    return False


def has_ubrique_text(entry: ET.Element) -> bool:
    return "ubrique" in ET.tostring(entry, encoding="unicode").lower()


def contracting_party_ids(entry: ET.Element):
    ids = []
    for el in entry.iter():
        if el.tag.split("}")[-1] == "LocatedContractingParty":
            for child in el.iter(f"{{{CBC}}}ID"):
                if child.text:
                    ids.append(child.text.strip())
            break
    return ids


def count_ubrique_in_zip_file(path: str):
    total = text_hits = filter_hits = 0
    missed = []
    with zipfile.ZipFile(path) as zf:
        for name in zf.namelist():
            if not name.endswith(".atom"):
                continue
            with zf.open(name) as f:
                try:
                    root = ET.parse(f).getroot()
                except ET.ParseError:
                    continue
                for entry in root.findall(f"{{{ATOM_NS}}}entry"):
                    total += 1
                    has_text = has_ubrique_text(entry)
                    passes   = is_ubrique_entry(entry)
                    text_hits   += has_text
                    filter_hits += passes
                    if has_text and not passes:
                        id_el    = entry.find(f"{{{ATOM_NS}}}id")
                        title_el = entry.find(f"{{{ATOM_NS}}}title")
                        missed.append({
                            "id":        id_el.text if id_el is not None else "?",
                            "title":     (title_el.text or "")[:80] if title_el is not None else "?",
                            "party_ids": contracting_party_ids(entry),
                        })
    return total, text_hits, filter_hits, missed


# ── Modos ─────────────────────────────────────────────────────────────────────

def cmd_discover(years: list) -> None:
    """Descubre qué URLs de ZIP existen para cada año/feed (sin descargar)."""
    print(f"Comprobando existencia de URLs para {len(years)} año(s)…\n")
    for year in years:
        print(f"-- {year} ----------------------------------")
        for feed, base in FEED_BASES.items():
            print(f"  [{feed}]", end=" ", flush=True)
            urls = discover_zip_urls(base, year)
            if not urls:
                print("ninguna URL encontrada (¿año inexistente?)")
            elif len(urls) == 1:
                print(f"1 ZIP  →  {urls[0]}")
            else:
                print(f"{len(urls)} ZIPs:")
                for u in urls:
                    print(f"    {u}")
        print()


def cmd_inspect(url: str) -> None:
    """Descarga un ZIP y muestra su estructura interna."""
    print(f"Descargando {url}")
    path = None
    try:
        path, _ = stream_to_tempfile(url)
        inspect_zip_file(path)
    finally:
        if path and os.path.exists(path):
            os.unlink(path)


def cmd_full(year: int) -> None:
    """Descarga + análisis completo Ubrique para un año."""
    for feed, base in FEED_BASES.items():
        urls = discover_zip_urls(base, year)
        if not urls:
            print(f"[{feed} {year}] Sin URLs — saltando")
            continue
        for url in urls:
            print(f"\n{'='*60}")
            print(f"Feed: {feed} ({year})")
            print(f"URL:  {url}")
            path = None
            try:
                path, _ = stream_to_tempfile(url)
                inspect_zip_file(path)
                total, text_hits, filter_hits, missed = count_ubrique_in_zip_file(path)
                print(f"\n--- Filtro Ubrique ---")
                print(f"  Total entradas:        {total}")
                print(f"  Con 'ubrique' (texto): {text_hits}")
                print(f"  Pasan el filtro:       {filter_hits}")
                print(f"  Texto sí, filtro NO:   {len(missed)}")
                if missed:
                    for m in missed[:20]:
                        print(f"    {m['id']}  {m['title']}  {m['party_ids']}")
                    if len(missed) > 20:
                        print(f"  … y {len(missed)-20} más")
            except Exception as e:
                print(f"ERROR: {e}")
            finally:
                if path and os.path.exists(path):
                    os.unlink(path)


# ── CLI ───────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Diagnóstico ZIPs PCSP — Ubrique")
    parser.add_argument("--year",    type=int, help="Año concreto")
    parser.add_argument("--inspect", metavar="URL", help="Descarga y muestra estructura de un ZIP")
    parser.add_argument("--full",    type=int, metavar="YEAR",
                        help="Análisis completo Ubrique para un año")
    args = parser.parse_args()

    if args.inspect:
        cmd_inspect(args.inspect)
    elif args.full:
        cmd_full(args.full)
    elif args.year:
        cmd_discover([args.year])
    else:
        years = list(range(2018, CURRENT_YEAR + 1))
        cmd_discover(years)


if __name__ == "__main__":
    main()
