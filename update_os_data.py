import json
import re
import urllib.request
from datetime import date, datetime, timezone


PRODUCTS = {
    "macOS": "macos",
    "iOS": "ios",
    "Android": "android",
    "Windows": "windows",
    "Windows Server": "windows-server",
    "Ubuntu": "ubuntu",
    "Red Hat Enterprise Linux": "rhel",
}

EOL_API = "https://endoflife.date/api/{product}.json"
APPLE_SECURITY_URL = "https://support.apple.com/en-us/100100"


def download_text(url):
    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": "Mozilla/5.0"
        }
    )

    with urllib.request.urlopen(request, timeout=30) as response:
        return response.read().decode("utf-8")


def get_eol_data(product):
    url = EOL_API.format(product=product)
    return json.loads(download_text(url))


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


def version_major(version):
    """
    Convert:
      26.6.2 -> 26
      15.7.9 -> 15
      18.7.10 -> 18
    """

    if not version:
        return None

    match = re.match(r"^(\d+)", str(version))

    if match:
        return match.group(1)

    return None


def version_tuple(version):
    """
    Makes versions sortable numerically.

    Example:
      26.6.2 -> (26, 6, 2)
      26.6   -> (26, 6)
    """

    try:
        return tuple(int(part) for part in version.split("."))
    except Exception:
        return tuple()


def get_apple_release_history():
    """
    Downloads Apple's security release page and extracts
    macOS and iOS version numbers.
    """

    html = download_text(APPLE_SECURITY_URL)

    macos_versions = []
    ios_versions = []

    # macOS examples:
    # macOS Tahoe 26.6.2
    # macOS Sequoia 15.7.9
    # macOS Sonoma 14.8.9

    macos_matches = re.findall(
        r"macOS\s+[A-Za-z][A-Za-z\s]*?\s+(\d+(?:\.\d+){1,2})",
        html,
        flags=re.IGNORECASE
    )

    # iOS examples:
    # iOS 26.6.1
    # iOS 18.7.10
    # iOS 16.7.16

    ios_matches = re.findall(
        r"\biOS\s+(\d+(?:\.\d+){1,2})",
        html,
        flags=re.IGNORECASE
    )

    for version in macos_matches:
        if version not in macos_versions:
            macos_versions.append(version)

    for version in ios_matches:
        if version not in ios_versions:
            ios_versions.append(version)

    return {
        "macOS": macos_versions,
        "iOS": ios_versions,
    }


def find_previous_apple_version(current_version, history):
    """
    Find the immediately previous Apple release
    within the same major version.

    Example:

      current = 15.7.9

      history contains:
        15.7.9
        15.7.8
        15.7.7

      result:
        15.7.8
    """

    if not current_version:
        return None

    major = version_major(current_version)

    same_major = [
        version
        for version in history
        if version_major(version) == major
    ]

    same_major = sorted(
        set(same_major),
        key=version_tuple,
        reverse=True
    )

    try:
        current_index = same_major.index(current_version)
    except ValueError:
        return None

    if current_index + 1 < len(same_major):
        return same_major[current_index + 1]

    return None


# ---------------------------------------------------------
# Get Apple release history
# ---------------------------------------------------------

print("Checking Apple security releases...")

try:
    apple_history = get_apple_release_history()

    print(
        f"Found {len(apple_history['macOS'])} macOS releases "
        f"and {len(apple_history['iOS'])} iOS releases."
    )

except Exception as error:

    print(f"Warning: Unable to read Apple security releases: {error}")

    apple_history = {
        "macOS": [],
        "iOS": [],
    }


# ---------------------------------------------------------
# Build output
# ---------------------------------------------------------

result = {
    "_last_updated": datetime.now(timezone.utc).isoformat(),
    "_sources": {
        "support": "https://endoflife.date",
        "apple_history": APPLE_SECURITY_URL,
    }
}


for display_name, product in PRODUCTS.items():

    print(f"Checking {display_name}...")

    releases = get_eol_data(product)

    supported = []
    unsupported = []


    for release in releases:

        latest = release.get("latest")

        entry = {
            "version": release.get("cycle"),
            "latest": latest,
            "eol": release.get("eol"),
        }


        # -------------------------------------------------
        # For Apple products, find the previous release
        # in the same major version.
        # -------------------------------------------------

        if display_name in ("macOS", "iOS"):

            previous = find_previous_apple_version(
                latest,
                apple_history[display_name]
            )

            entry["previous"] = previous


        if is_supported(release):
            supported.append(entry)
        else:
            unsupported.append(entry)


    result[display_name] = {
        "supported": supported,
        "previous_unsupported": unsupported[:1],
    }


# ---------------------------------------------------------
# Write JSON
# ---------------------------------------------------------

with open("os-support.json", "w", encoding="utf-8") as file:

    json.dump(
        result,
        file,
        indent=2,
        ensure_ascii=False
    )


print("OS support data updated.")
