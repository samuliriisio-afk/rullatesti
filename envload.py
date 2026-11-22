"""Lukee .env-tiedoston ympäristömuuttujiksi (jos tiedosto on olemassa). Tuodaan ensimmäisenä."""
import os
from pathlib import Path

p = Path(__file__).parent / ".env"
if p.exists():
    for line in p.read_text("utf-8-sig").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))
