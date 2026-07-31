"""
Lee todos los ficheros .log de una carpeta (los que hayas guardado con
    docker compose up --build | tee nombre.log
y saca un CSV resumen con las metricas de cada ejecucion, listo para
abrir en Excel.

Uso:
    python summarize_logs.py <carpeta_con_logs> [salida.csv]

Si no das el segundo argumento, escribe "benchmark_summary.csv" en la
carpeta actual.
"""

import csv
import re
import sys
from pathlib import Path


def read_log_text(path: Path) -> str:
    """Lee el log detectando la codificacion automaticamente. PowerShell
    (tee / Tee-Object) suele guardar en UTF-16 con BOM, mientras que en
    Linux/macOS suele ser UTF-8 -- detectamos por el BOM en vez de
    asumir uno de los dos."""
    raw = path.read_bytes()
    if raw.startswith(b"\xff\xfe") or raw.startswith(b"\xfe\xff"):
        return raw.decode("utf-16", errors="ignore")
    if raw.startswith(b"\xef\xbb\xbf"):
        return raw.decode("utf-8-sig", errors="ignore")
    return raw.decode("utf-8", errors="ignore")


def parse_log(text: str) -> dict:
    result = {
        "n_steps": None,
        "n_parties": None,
        "time_seconds_party0": None,
        "data_sent_party0_mb": None,
        "global_data_mb": None,
        "vm_rounds": None,
        "bit_triples": None,
        "bit_opens": None,
    }

    m = re.search(r"n_steps=(\d+),\s*n_parties=(\d+)", text)
    if m:
        result["n_steps"] = int(m.group(1))
        result["n_parties"] = int(m.group(2))

    # "Time = 7.15113 seconds" -- cogemos la primera ocurrencia (party0)
    m = re.search(r"Time = ([\d.]+) seconds", text)
    if m:
        result["time_seconds_party0"] = float(m.group(1))

    # "Data sent = 6.51698 MB in ~96602 rounds (party 0 only; ...)"
    m = re.search(r"Data sent = ([\d.]+) MB.*\(party 0 only", text)
    if m:
        result["data_sent_party0_mb"] = float(m.group(1))

    # "Global data sent = 19.351 MB (all parties)"
    m = re.search(r"Global data sent = ([\d.]+) MB", text)
    if m:
        result["global_data_mb"] = float(m.group(1))

    # "24122 virtual machine rounds"
    m = re.search(r"(\d+)\s+virtual machine rounds", text)
    if m:
        result["vm_rounds"] = int(m.group(1))

    # "338595 bit triples"
    m = re.search(r"(\d+)\s+bit triples", text)
    if m:
        result["bit_triples"] = int(m.group(1))

    # "512 bit opens"
    m = re.search(r"(\d+)\s+bit opens", text)
    if m:
        result["bit_opens"] = int(m.group(1))

    return result


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)

    log_dir = Path(sys.argv[1])
    out_path = Path(sys.argv[2]) if len(sys.argv) > 2 else Path("benchmark_summary.csv")

    log_files = sorted(log_dir.glob("*.log"))
    if not log_files:
        print(f"No se encontraron ficheros .log en {log_dir}")
        sys.exit(1)

    rows = []
    for f in log_files:
        text = read_log_text(f)
        parsed = parse_log(text)
        parsed["file"] = f.name
        rows.append(parsed)

    fieldnames = [
        "file", "n_steps", "n_parties", "time_seconds_party0",
        "data_sent_party0_mb", "global_data_mb", "vm_rounds",
        "bit_triples", "bit_opens",
    ]

    with out_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    print(f"Escritas {len(rows)} filas en {out_path}")


if __name__ == "__main__":
    main()