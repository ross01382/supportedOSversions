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


# ----------------------------------------------------------
# Download helper
# ----------------------------------------------------------

def download_text(url):

    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": "Mozilla/5.0"
        }
    )

    with urllib.request.urlopen(
        request,
        timeout=30
    ) as response:

        return response.read().decode(
            "utf-8",
            errors="ignore"
        )


# ----------------------------------------------------------
# Get endoflife.date data
# ----------------------------------------------------------

def get_eol_data(product):

    url = EOL_API.format(
        product=product
    )

    return json.loads(
        download_text(url)
    )


# ----------------------------------------------------------
# Is release supported?
# ----------------------------------------------------------

def is_supported(item):

    eol = item.get("eol")

    if eol is False or eol is None:
        return True

    if isinstance(eol, str):

        try:

            return (
                date.fromisoformat(eol)
                >= date.today()
            )

        except ValueError:

            return False

    return False


# ----------------------------------------------------------
# Version helpers
# ----------------------------------------------------------

def version_major(version):

    if not version:
        return None

    match = re.match(
        r"^(\d+)",
        str(version)
    )

    if match:
        return match.group(1)

    return None


def version_tuple(version):

    try:

        return tuple(
            int(part)
            for part in version.split(".")
        )

    except Exception:

        return tuple()


# ----------------------------------------------------------
# Apple release history
# ----------------------------------------------------------

def get_apple_release_history():

    html = download_text(
        APPLE_SECURITY_URL
    )

    text = re.sub(
        r"<[^>]+>",
        " ",
        html
    )

    text = (
        text
        .replace("&nbsp;", " ")
        .replace("&#x27;", "'")
        .replace("&amp;", "&")
    )

    macos_versions = re.findall(
        r"macOS\s+[A-Za-z]+\s+"
        r"(\d+(?:\.\d+){1,2})",
        text,
        flags=re.IGNORECASE
    )

    ios_versions = re.findall(
        r"\biOS\s+"
        r"(\d+(?:\.\d+){1,2})",
        text,
        flags=re.IGNORECASE
    )

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


# ----------------------------------------------------------
# Previous Apple minor/security release
# ----------------------------------------------------------

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

    try:

        current_index = same_major.index(
            current_version
        )

    except ValueError:

        return None

    if current_index + 1 < len(same_major):

        return same_major[
            current_index + 1
        ]

    return None


# ----------------------------------------------------------
# Windows helper
# ----------------------------------------------------------

def windows_version_number(cycle):

    match = re.search(
        r"-(\d+h\d+|\d{4})",
        cycle,
        flags=re.IGNORECASE
    )

    if not match:
        return None

    return match.group(1).upper()


def get_windows_entries(releases):

    supported_by_name = {}
    unsupported = []

    for release in releases:

        cycle = str(
            release.get(
                "cycle",
                ""
            )
        ).lower()

        latest = release.get(
            "latest"
        )

        eol = release.get(
            "eol"
        )

        lts = bool(
            release.get(
                "lts",
                False
            )
        )

        # Ignore IoT releases
        if "iot" in cycle:
            continue

        version = windows_version_number(
            cycle
        )

        if not version:
            continue

        display_name = None

        # --------------------------------------------------
        # Windows 11 LTSC
        # --------------------------------------------------

        if (
            cycle.startswith("11-")
            and lts
        ):

            display_name = (
                f"11 {version} LTSC"
            )

        # --------------------------------------------------
        # Windows 11 normal editions
        # --------------------------------------------------

        elif cycle.startswith("11-"):

            # Enterprise / Education release
            if "-e" in cycle:

                display_name = (
                    f"11 {version} "
                    f"Enterprise/Education"
                )

            # Home / Pro release
            elif "-w" in cycle:

                display_name = (
                    f"11 {version}"
                )

            else:

                display_name = (
                    f"11 {version}"
                )

        # --------------------------------------------------
        # Windows 10 LTSC / LTSB
        # --------------------------------------------------

        elif (
            cycle.startswith("10-")
            and lts
        ):

            if version == "21H2":

                display_name = (
                    "10 LTSC 2021"
                )

            elif version == "1809":

                display_name = (
                    "10 LTSC 2019"
                )

            elif version == "1607":

                display_name = (
                    "10 LTSB 2016"
                )

            elif version == "1507":

                display_name = (
                    "10 LTSB 2015"
                )

            else:

                display_name = (
                    f"10 {version} LTSC"
                )

        # --------------------------------------------------
        # Normal Windows 10
        # --------------------------------------------------

        elif cycle.startswith("10-"):

            display_name = (
                f"10 {version}"
            )

        else:

            continue

        entry = {
            "version": display_name,
            "latest": latest,
            "eol": eol,
        }

        if is_supported(release):

            existing = supported_by_name.get(
                display_name
            )

            if existing is None:

                supported_by_name[
                    display_name
                ] = entry

            else:

                # Prefer whichever entry has a usable
                # build number.
                if (
                    not existing.get("latest")
                    and latest
                ):

                    supported_by_name[
                        display_name
                    ] = entry

        else:

            unsupported.append(
                entry
            )

    supported = list(
        supported_by_name.values()
    )

    # ------------------------------------------------------
    # Remove duplicate Windows 11 rows where:
    #
    # 11 25H2
    # 11 25H2 Enterprise/Education
    #
    # are both supported.
    #
    # In that situation the simple row is sufficient.
    #
    # However if Home/Pro has expired and Enterprise/
    # Education remains supported, keep the edition label.
    # ------------------------------------------------------

    simple_supported_versions = set()

    for entry in supported:

        match = re.fullmatch(
            r"11 (\d+H\d+)",
            entry["version"]
        )

        if match:

            simple_supported_versions.add(
                match.group(1)
            )

    cleaned_supported = []

    for entry in supported:

        match = re.fullmatch(
            r"11 (\d+H\d+) Enterprise/Education",
            entry["version"]
        )

        if (
            match
            and match.group(1)
            in simple_supported_versions
        ):

            continue

        cleaned_supported.append(
            entry
        )

    supported = cleaned_supported

    # ------------------------------------------------------
    # Sort Windows rows
    # ------------------------------------------------------

    def windows_sort_key(entry):

        name = entry["version"]

        # Windows 11 first
        if name.startswith("11 "):

            version_match = re.search(
                r"(\d+)H(\d+)",
                name
            )

            if version_match:

                return (
                    0,
                    -int(version_match.group(1)),
                    -int(version_match.group(2)),
                    0 if "LTSC" in name else 1
                )

            return (
                0,
                0,
                0,
                0
            )

        # Windows 10 LTSC/LTSB
        if name.startswith("10 "):

            if "2021" in name:
                rank = 0

            elif "2019" in name:
                rank = 1

            elif "2016" in name:
                rank = 2

            elif "2015" in name:
                rank = 3

            else:
                rank = 4

            return (
                1,
                rank,
                0,
                0
            )

        return (
            9,
            9,
            9,
            9
        )

    supported.sort(
        key=windows_sort_key
    )

    # ------------------------------------------------------
    # Previous unsupported Windows release
    # ------------------------------------------------------

    preferred_previous = None

    for entry in unsupported:

        if entry["version"] == "10 22H2":

            preferred_previous = entry
            break

    if (
        preferred_previous is None
        and unsupported
    ):

        preferred_previous = unsupported[0]

    previous_unsupported = []

    if preferred_previous:

        previous_unsupported.append(
            preferred_previous
        )

    return (
        supported,
        previous_unsupported
    )


# ----------------------------------------------------------
# Apple history
# ----------------------------------------------------------

print(
    "Checking Apple security releases..."
)

try:

    apple_history = (
        get_apple_release_history()
    )

except Exception as error:

    print(
        "Warning: Unable to read Apple security releases:",
        error
    )

    apple_history = {
        "macOS": [],
        "iOS": [],
    }


# ----------------------------------------------------------
# Output
# ----------------------------------------------------------

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


# ----------------------------------------------------------
# Process operating systems
# ----------------------------------------------------------

for display_name, product in PRODUCTS.items():

    print(
        f"Checking {display_name}..."
    )

    releases = get_eol_data(
        product
    )

    # ------------------------------------------------------
    # Windows special handling
    # ------------------------------------------------------

    if display_name == "Windows":

        supported, unsupported = (
            get_windows_entries(
                releases
            )
        )

        result[display_name] = {
            "supported": supported,
            "unsupported": unsupported,
        }

        continue

    # ------------------------------------------------------
    # Other OS
    # ------------------------------------------------------

    supported = []
    unsupported = []

    for release in releases:

        latest = release.get(
            "latest"
        )

        entry = {

            "version":
                release.get(
                    "cycle"
                ),

            "latest":
                latest,

            "eol":
                release.get(
                    "eol"
                ),

        }

        # Apple previous minor/security release
        if display_name in (
            "macOS",
            "iOS"
        ):

            entry["previous"] = (
                find_previous_apple_version(
                    latest,
                    apple_history[
                        display_name
                    ]
                )
            )

        if is_supported(release):

            supported.append(
                entry
            )

        else:

            unsupported.append(
                entry
            )

    # Only show one previous unsupported release
    if unsupported:

        unsupported = [
            unsupported[0]
        ]

    result[display_name] = {
        "supported": supported,
        "unsupported": unsupported,
    }


# ----------------------------------------------------------
# Write JSON
# ----------------------------------------------------------

with open(
    "os-support.json",
    "w",
    encoding="utf-8"
) as file:

    json.dump(
        result,
        file,
        indent=2
    )


print(
    "os-support.json updated successfully."
)
