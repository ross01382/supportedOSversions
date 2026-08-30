#!/usr/bin/env python3
"""
Build os-data.json for the GitHub Pages OS support dashboard.

Strategy
--------
1. endoflife.date supplies cross-platform lifecycle/support-cycle data.
2. Apple's Security Releases page is used to enrich macOS/iOS cycles with
   the latest point release Apple has actually published for each cycle.
3. Microsoft's Windows Release Health pages are used to enrich Windows and
   Windows Server records with current builds when matching rows are found.
4. Exactly one unsupported release cycle is included: the newest EOL cycle
   by version, after all currently-supported cycles.

If an official-vendor enrichment fails, the build does NOT fail: it falls
back to endoflife.date's latest version value.
"""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import requests
from bs4 import BeautifulSoup

TIMEOUT = 30
HEADERS = {
    "User-Agent": "os-support-dashboard/1.0 (+GitHub Actions; lifecycle dashboard)"
}

EOL_API = "https://endoflife.date/api/v1/products/{product}/"
APPLE_URL = "https://support.apple.com/en-us/100100"
WINDOWS_URL = "https://learn.microsoft.com/en-us/windows/release-health/windows11-release-information"
SERVER_URL = "https://learn.microsoft.com/en-us/windows/release-health/windows-server-release-info"

PRODUCTS = [
    ("macos", "macOS"),
    ("ios", "iOS"),
    ("android", "Android"),
    ("windows", "Windows"),
    ("windows-server", "Windows Server"),
    ("ubuntu", "Ubuntu"),
    ("rhel", "Red Hat Enterprise Linux"),
]


def get(url: str) -> requests.Response:
    r = requests.get(url, headers=HEADERS, timeout=TIMEOUT)
    r.raise_for_status()
    return r


def version_key(value: str) -> tuple:
    """Natural-ish numeric ordering for values such as 26, 25H2, 14.8.9, 2025."""
    parts = re.findall(r"\d+|[A-Za-z]+", str(value))
    out = []
    for p in parts:
        out.append((0, int(p)) if p.isdigit() else (1, p.lower()))
    return tuple(out)


def parse_iso_date(value: Any) -> str | None:
    if not value or value is False:
        return None
    return str(value)[:10]


def load_eol(product: str) -> dict:
    payload = get(EOL_API.format(product=product)).json()
    return payload["result"]


def select_releases(product: dict) -> list[dict]:
    releases = product.get("releases", [])

    supported = [
        r for r in releases
        if r.get("isEol") is False or r.get("isMaintained") is True
    ]

    unsupported = [
        r for r in releases
        if r.get("isEol") is True
    ]

    # "Previous unsupported" means the highest-version EOL cycle,
    # not merely whichever happened to have the most recent EOL date.
    unsupported.sort(key=lambda r: version_key(r.get("label") or r.get("name") or ""), reverse=True)

    chosen = supported + unsupported[:1]

    def supported_first_sort(r: dict):
        status = 0 if (r.get("isEol") is False or r.get("isMaintained") is True) else 1
        return (status,)

    # Keep vendor/API ordering for supported releases, append exactly one EOL cycle.
    return chosen


def base_record(r: dict) -> dict:
    cycle = str(r.get("label") or r.get("name") or "")
    latest = r.get("latest") or {}
    version = str(latest.get("name") or cycle)

    unsupported = r.get("isEol") is True and r.get("isMaintained") is not True

    return {
        "cycle": cycle,
        "version": version,
        "build": None,
        "status": "unsupported" if unsupported else "supported",
        "eol": parse_iso_date(r.get("eolFrom")),
    }


def apple_latest_by_cycle() -> tuple[dict[str, str], dict[str, str]]:
    """
    Return ({macOS major: latest point release}, {iOS major: latest point release})
    from Apple's Security Releases table.

    The table may contain many entries for the same cycle. We keep the highest
    semantic version observed for each major.
    """
    html = get(APPLE_URL).text
    soup = BeautifulSoup(html, "html.parser")
    text = soup.get_text("\n", strip=True)

    mac: dict[str, str] = {}
    ios: dict[str, str] = {}

    # Matches strings such as "macOS Sequoia 15.7.9", "macOS Tahoe 26.6.2"
    for m in re.finditer(r"\bmacOS(?:\s+[A-Za-z][A-Za-z -]+)?\s+(\d+(?:\.\d+){1,2})\b", text):
        ver = m.group(1)
        major = ver.split(".")[0]
        if major not in mac or version_key(ver) > version_key(mac[major]):
            mac[major] = ver

    # Matches "iOS 26.6.1 and iPadOS..." and standalone iOS versions.
    for m in re.finditer(r"\biOS\s+(\d+(?:\.\d+){1,2})\b", text):
        ver = m.group(1)
        major = ver.split(".")[0]
        if major not in ios or version_key(ver) > version_key(ios[major]):
            ios[major] = ver

    return mac, ios


def enrich_apple(records_by_id: dict[str, dict]) -> None:
    try:
        mac, ios = apple_latest_by_cycle()
    except Exception as exc:
        print(f"Apple enrichment skipped: {exc}")
        return

    for product_id, lookup in (("macos", mac), ("ios", ios)):
        for r in records_by_id[product_id]["releases"]:
            major = re.match(r"\d+", r["cycle"])
            if major and major.group(0) in lookup:
                r["version"] = lookup[major.group(0)]
        records_by_id[product_id]["source"] = APPLE_URL
        records_by_id[product_id]["enriched_from"] = "Apple Security Releases"


def microsoft_build_map(url: str) -> dict[str, str]:
    """
    Extract likely version/build pairs from Microsoft Learn Release Health HTML.

    This intentionally uses a broad text parser rather than brittle CSS selectors.
    It looks for Windows version labels near OS build numbers.
    """
    html = get(url).text
    soup = BeautifulSoup(html, "html.parser")
    text = soup.get_text(" ", strip=True)
    mapping: dict[str, str] = {}

    # Client: "Version 25H2 ... 26200.9168"
    for m in re.finditer(
        r"(?:Version\s+)?(\d{2}H[12]).{0,700}?(\d{5}\.\d{3,6})",
        text,
        flags=re.I,
    ):
        mapping.setdefault(m.group(1).upper(), m.group(2))

    # Server: "Windows Server 2025 ... 26100.33296"
    for m in re.finditer(
        r"Windows Server\s+(20\d{2}).{0,700}?(\d{5}\.\d{3,6})",
        text,
        flags=re.I,
    ):
        mapping.setdefault(m.group(1), m.group(2))

    return mapping


def enrich_microsoft(records_by_id: dict[str, dict]) -> None:
    try:
        win_builds = microsoft_build_map(WINDOWS_URL)
        for r in records_by_id["windows"]["releases"]:
            for key, build in win_builds.items():
                if key.lower() in r["cycle"].lower():
                    r["build"] = build
                    break
        records_by_id["windows"]["source"] = WINDOWS_URL
        records_by_id["windows"]["enriched_from"] = "Microsoft Windows Release Health"
    except Exception as exc:
        print(f"Windows enrichment skipped: {exc}")

    try:
        server_builds = microsoft_build_map(SERVER_URL)
        for r in records_by_id["windows-server"]["releases"]:
            for key, build in server_builds.items():
                if key in r["cycle"]:
                    r["build"] = build
                    break
        records_by_id["windows-server"]["source"] = SERVER_URL
        records_by_id["windows-server"]["enriched_from"] = "Microsoft Windows Server Release Health"
    except Exception as exc:
        print(f"Windows Server enrichment skipped: {exc}")


def main() -> None:
    products = []
    records_by_id: dict[str, dict] = {}

    for product_id, display_name in PRODUCTS:
        raw = load_eol(product_id)
        selected = select_releases(raw)
        record = {
            "id": product_id,
            "name": display_name,
            "source": raw.get("links", {}).get("html") or f"https://endoflife.date/{product_id}",
            "enriched_from": None,
            "releases": [base_record(r) for r in selected],
        }
        products.append(record)
        records_by_id[product_id] = record

    enrich_apple(records_by_id)
    enrich_microsoft(records_by_id)

    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "products": products,
    }

    out = Path(__file__).resolve().parent / "os-data.json"
    out.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    print(f"Wrote {out}")


if __name__ == "__main__":
    main()
