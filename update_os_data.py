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
# endoflife.date
# ----------------------------------------------------------

def get_eol_data(product):

    url = EOL_API.format(
        product=product
    )

    return json.loads(
        download_text(url)
    )


# ----------------------------------------------------------
# Is a release still supported?
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
#
# Used so macOS/iOS can show:
#
#   Supported version    Previous release
#   26.6.2               26.6.1
#
# ----------------------------------------------------------

def get_apple_release_history():

    html = download_text(
        APPLE_SECURITY_URL
    )

    # Remove HTML tags
    text = re.sub(
        r"<[^>]+>",
        " ",
        html
    )

    # Decode common entities
    text = (
        text
        .replace("&nbsp;", " ")
        .replace("&#x27;", "'")
        .replace("&amp;", "&")
    )


    # macOS examples:
    #
    # macOS Tahoe 26.6.2
    # macOS Sequoia 15.7.9

    macos_versions = re.findall(
        r"macOS\s+[A-Za-z]+\s+"
        r"(\d+(?:\.\d+){1,2})",
        text,
        flags=re.IGNORECASE
    )


    # iOS examples:
    #
    # iOS 26.6.1
    # iOS 18.7.10

    ios_versions = re.findall(
        r"\biOS\s+"
        r"(\d+(?:\.\d+){1,2})",
        text,
        flags=re.IGNORECASE
    )


    # Remove duplicates,
    # preserving original order

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
# Find previous Apple minor/security release
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

        if version_major(version)
        == major

    ]


    same_major = sorted(
        set(same_major),
        key=version_tuple,
        reverse=True
    )


    print(
        f"Looking for previous version "
        f"of {current_version}. "
        f"Candidates: "
        f"{same_major[:10]}"
    )


    try:

        current_index = (
            same_major.index(
                current_version
            )
        )

    except ValueError:

        return None


    if (
        current_index + 1
        < len(same_major)
    ):

        return same_major[
            current_index + 1
        ]


    return None


# ----------------------------------------------------------
# WINDOWS
# ----------------------------------------------------------
#
# endoflife.date distinguishes releases using values such as:
#
# 11-26h1-e
# 11-26h1-w
# 11-24h2-e-lts
# 10-21h2-e-lts
# 10-1809-e-lts
# 10-1607-e-lts
#
# We combine ordinary Windows 11 editions where appropriate
# but keep LTSC/LTSB as separate rows.
# ----------------------------------------------------------

def get_windows_entries(releases):

    supported = []
    unsupported = []


    # Used to avoid duplicate rows.
    #
    # For example:
    #
    # 11-25h2-e
    # 11-25h2-w
    #
    # become:
    #
    # Windows 11 25H2

    seen_supported = set()
    seen_unsupported = set()


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


        # ------------------------------------------
        # Ignore IoT releases
        # ------------------------------------------

        if "iot" in cycle:
            continue


        entry = None


        # ------------------------------------------
        # WINDOWS 11 LTSC
        # ------------------------------------------

        match = re.match(
            r"11-(\d+h\d+)-e-lts$",
            cycle
        )

        if match:

            release_version = (
                match
                .group(1)
                .upper()
            )

            entry = {
                "version":
                    f"Windows 11 "
                    f"{release_version} LTSC",

                "latest":
                    latest,

                "eol":
                    eol,
            }


        # ------------------------------------------
        # NORMAL WINDOWS 11
        # ------------------------------------------

        elif cycle.startswith("11-"):

            match = re.match(
                r"11-(\d+h\d+)",
                cycle
            )

            if not match:
                continue

            release_version = (
                match
                .group(1)
                .upper()
            )


            # We deliberately combine Home/Pro and
            # Enterprise/Education where at least
            # one edition is still supported.
            #
            # That keeps the dashboard compact.

            entry = {
                "version":
                    f"Windows 11 "
                    f"{release_version}",

                "latest":
                    latest,

                "eol":
                    eol,
            }


        # ------------------------------------------
        # WINDOWS 10 LTSC / LTSB
        # ------------------------------------------

        elif (
            cycle.startswith("10-")
            and lts
        ):

            match = re.match(
                r"10-"
                r"([0-9]+h[0-9]+|\d{4})"
                r"-e-lts",
                cycle
            )

            if not match:
                continue


            release_version = (
                match
                .group(1)
                .upper()
            )


            if release_version == "21H2":

                display_name = (
                    "Windows 10 "
                    "LTSC 2021"
                )

            elif release_version == "1809":

                display_name = (
                    "Windows 10 "
                    "LTSC 2019"
                )

            elif release_version == "1607":

                display_name = (
                    "Windows 10 "
                    "LTSB 2016"
                )

            elif release_version == "1507":

                display_name = (
                    "Windows 10 "
                    "LTSB 2015"
                )

            else:

                display_name = (
                    "Windows 10 "
                    f"{release_version} LTSC"
                )


            entry = {
                "version":
                    display_name,

                "latest":
                    latest,

                "eol":
                    eol,
            }


        # ------------------------------------------
        # NORMAL WINDOWS 10
        # ------------------------------------------

        elif cycle.startswith("10-"):

            match = re.match(
                r"10-"
                r"([0-9]+h[0-9]+|\d{4})",
                cycle
            )

            if not match:
                continue


            release_version = (
                match
                .group(1)
                .upper()
            )


            entry = {
                "version":
                    f"Windows 10 "
                    f"{release_version}",

                "latest":
                    latest,

                "eol":
                    eol,
            }


        else:

            continue


        # ------------------------------------------
        # Supported
        # ------------------------------------------

        if is_supported(release):

            key = (
                entry["version"],
                entry["latest"]
            )

            if key not in seen_supported:

                supported.append(
                    entry
                )

                seen_supported.add(
                    key
                )


        # ------------------------------------------
        # Unsupported
        # ------------------------------------------

        else:

            key = (
                entry["version"],
                entry["latest"]
            )

            if key not in seen_unsupported:

                unsupported.append(
                    entry
                )

                seen_unsupported.add(
                    key
                )


    # ------------------------------------------------------
    # Windows 11 editions can have different EOL dates.
    #
    # If one edition of a release is supported and another
    # is unsupported, we don't want the same version shown
    # in BOTH sections.
    #
    # Remove an unsupported row when that version already
    # exists in supported.
    # ------------------------------------------------------

    supported_names = {
        item["version"]
        for item in supported
    }


    unsupported = [

        item

        for item in unsupported

        if item["version"]
        not in supported_names

    ]


    # ------------------------------------------------------
    # We only want ONE previous unsupported Windows release.
    #
    # Prefer Windows 10 22H2 because it is the most useful
    # "normal" previous release for this dashboard.
    # ------------------------------------------------------

    preferred_previous = None


    for entry in unsupported:

        if (
            entry["version"]
            == "Windows 10 22H2"
        ):

            preferred_previous = entry
            break


    if preferred_previous is None:

        if unsupported:
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
        "Warning: Unable to read "
        "Apple security releases: "
        f"{error}"
    )

    apple_history = {
        "macOS": [],
        "iOS": [],
    }


# ----------------------------------------------------------
# Output structure
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
# Process each operating system
# ----------------------------------------------------------

for display_name, product in (
    PRODUCTS.items()
):

    print(
        f"Checking "
        f"{display_name}..."
    )


    releases = get_eol_data(
        product
    )


    # ------------------------------------------------------
    # Windows uses special handling
    # ------------------------------------------------------

    if display_name == "Windows":

        (
            supported,
            unsupported
        ) = get_windows_entries(
            releases
        )


        result[display_name] = {

            "supported":
                supported,

            "unsupported":
                unsupported,

        }


        continue


    # ------------------------------------------------------
    # Everything except Windows
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


        # --------------------------------------------------
        # Apple:
        # Add previous minor/security release
        # --------------------------------------------------

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


    # ------------------------------------------------------
    # Only keep the most recent unsupported major release
    # ------------------------------------------------------

    if unsupported:

        unsupported = [
            unsupported[0]
        ]


    result[display_name] = {

        "supported":
            supported,

        "unsupported":
            unsupported,

    }


# ----------------------------------------------------------
# Write JSON file
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
