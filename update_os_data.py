import json
import urllib.request
from datetime import date

PRODUCTS = {
    "macOS": "macos",
    "iOS": "ios",
    "Android": "android",
    "Windows": "windows",
    "Windows Server": "windows-server",
    "Ubuntu": "ubuntu",
    "Red Hat Enterprise Linux": "rhel",
}

API = "https://endoflife.date/api/{product}.json"


def get_data(product):
    url = API.format(product=product)

    with urllib.request.urlopen(url) as response:
        return json.loads(response.read().decode())


def is_supported(item):
    eol = item.get("eol")

    if eol is False or eol is None:
        return True

    if isinstance(eol, str):
        try:
            return date.fromisoformat(eol) >= date.today()
        except ValueError:
            return False

    return False


result = {}

for display_name, product in PRODUCTS.items():
    print(f"Checking {display_name}...")

    releases = get_data(product)

    supported = []
    unsupported = []

    for release in releases:
        entry = {
            "version": release.get("cycle"),
            "latest": release.get("latest"),
            "eol": release.get("eol"),
        }

        if is_supported(release):
            supported.append(entry)
        else:
            unsupported.append(entry)

    result[display_name] = {
        "supported": supported,
        "previous_unsupported": unsupported[:1],
    }


with open("os-support.json", "w", encoding="utf-8") as f:
    json.dump(result, f, indent=2)

print("OS support data updated.")
