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
        return response.read().decode("utf-8", errors="ignore")


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
    if not version:
        return None

    match = re.match(r"^(\d+)", str(version))

    if match:
        return match.group(1)

    return None


def version_tuple(version):
    try:
        return tuple(
            int(part)
            for part in str(version).split(".")
        )
    except Exception:
        return tuple()


def windows_sort_key(entry):
    version = str(entry.get("version", ""))

    match = re.match(
        r"^(\d{2})H([12])$",
        version
    )

    if match:
        year = int(match.group(1))
        half = int(match.group(2))

        return year, half

    return 0, 0


def clean_windows_releases(releases):
    """
    Convert endoflife.date Windows entries such as:

    11-25h2-e
    11-25h2-w
    11-24h2-e
    11-24h2-w

    into one clean entry per Windows 11 release:

    25H2
    24H2
    23H2

    Prefer the Workstation/Home/Pro (-w) entry where available,
    because that is the normal desktop Windows lifecycle.
    """

    grouped = {}

    for release in releases:

        cycle = str(
            release.get("cycle", "")
        ).strip().lower()

        match = re.match(
            r"^11-(\d{2}h[12])-(w|e)$",
            cycle
        )

        if not match:
            continue

        friendly_version = (
            match.group(1).upper()
        )

        edition = match.group(2)

        # Prefer the normal workstation/Home/Pro entry (-w)
        if (
            friendly_version not in grouped
            or edition == "w"
        ):

            cleaned_release = dict(
                release
            )

            cleaned_release["cycle"] = (
                friendly_version
            )

            grouped[
                friendly_version
            ] = cleaned_release


    cleaned = list(
        grouped.values()
    )

    cleaned.sort(
        key=lambda release:
            windows_sort_key(
                {
                    "version":
                        release.get("cycle")
                }
            ),
        reverse=True
    )

    return cleaned


def get_apple_release_history():

    html = download_text(
        APPLE_SECURITY_URL
    )

    # Remove HTML tags so we are matching
    # visible text rather than page markup
    text = re.sub(
        r"<[^>]+>",
        " ",
        html
    )

    # Decode common HTML entities
    text = (
        text
        .replace("&nbsp;", " ")
        .replace("&#x27;", "'")
        .replace("&amp;", "&")
    )

    macos_versions = re.findall(
        r"macOS\s+[A-Za-z]+\s+(\d+(?:\.\d+){1,2})",
        text,
        flags=re.IGNORECASE
    )

    ios_versions = re.findall(
        r"\biOS\s+(\d+(?:\.\d+){1,2})",
        text,
        flags=re.IGNORECASE
    )

    # Remove duplicates while preserving order
    macos_versions = list(
        dict.fromkeys(
            macos_versions
        )
    )

    ios_versions = list(
        dict.fromkeys(
            ios_versions
        )
    )

    print(
        "Apple macOS versions found:",
        macos_versions[:20]
    )

    print(
        "Apple iOS versions found:",
        ios_versions[:20]
    )

    return {
        "macOS": macos_versions,
        "iOS": ios_versions,
    }


def find_previous_apple_version(
    current_version,
    history
):

    if not current_version:
        return None

    major = version_major(
        current_version
    )

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

    print(
        f"Looking for previous version "
        f"of {current_version}. "
        f"Candidates: {same_major[:10]}"
    )

    try:
        current_index = same_major.index(
            current_version
        )
    except ValueError:
        return None

    if current_index + 1 < len(
        same_major
    ):
        return same_major[
            current_index + 1
        ]

    return None


print(
    "Checking Apple security releases..."
)

try:

    apple_history = (
        get_apple_release_history()
    )

except Exception as error:

    print(
        "Warning: Unable to read "
        f"Apple security releases: {error}"
    )

    apple_history = {
        "macOS": [],
        "iOS": [],
    }


result = {
    "_last_updated":
        datetime.now(
            timezone.utc
        ).isoformat(),

    "_sources": {
        "support":
            "https://endoflife.date",

        "apple_history":
            APPLE_SECURITY_URL,
    }
}


for display_name, product in PRODUCTS.items():

    print(
        f"Checking {display_name}..."
    )

    try:

        releases = get_eol_data(
            product
        )

    except Exception as error:

        print(
            f"Warning: Unable to get "
            f"{display_name}: {error}"
        )

        result[display_name] = {
            "supported": [],
            "previous_unsupported": [],
        }

        continue


    #
    # Windows cleanup
    #

    if display_name == "Windows":

        releases = clean_windows_releases(
            releases
        )


    supported = []
    unsupported = []


    for release in releases:

        latest = release.get(
            "latest"
        )

        entry = {
            "version":
                release.get("cycle"),

            "latest":
                latest,

            "eol":
                release.get("eol"),
        }


        #
        # Apple previous minor version
        #

        if display_name in (
            "macOS",
            "iOS"
        ):

            previous = (
                find_previous_apple_version(
                    latest,
                    apple_history[
                        display_name
                    ]
                )
            )

            entry["previous"] = (
                previous
            )


        if is_supported(release):

            supported.append(
                entry
            )

        else:

            unsupported.append(
                entry
            )


    #
    # Sort Windows releases
    #

    if display_name == "Windows":

        supported.sort(
            key=windows_sort_key,
            reverse=True
        )

        unsupported.sort(
            key=windows_sort_key,
            reverse=True
        )


    result[display_name] = {
        "supported":
            supported,

        "previous_unsupported":
            unsupported[:1],
    }


with open(
    "os-support.json",
    "w",
    encoding="utf-8"
) as file:

    json.dump(
        result,
        file,
        indent=2,
        ensure_ascii=False
    )


print(
    "OS support data updated."
)
