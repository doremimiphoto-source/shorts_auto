"""MeloTTS PyPI 패키지 메타데이터 확인 (임시)."""
from __future__ import annotations

import httpx

for name in ["melotts", "MeloTTS"]:
    r = httpx.get(f"https://pypi.org/pypi/{name}/json", timeout=15)
    if r.status_code != 200:
        print(f"{name}: 404")
        continue
    d = r.json()["info"]
    print(f"== {name} ==")
    print(f"  version: {d.get('version')}")
    print(f"  author : {d.get('author')}")
    print(f"  license: {d.get('license')}")
    print(f"  home   : {d.get('home_page')}")
    print(f"  summary: {(d.get('summary') or '')[:100]}")
    print()
