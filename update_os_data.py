import json
import re
import urllib.request
from datetime import date, datetime, timezone


# ============================================================
# SOURCES
# ============================================================

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

APPLE_SECURITY_URL = (
    "https://support.apple.com/en-us/100100"
)

CHROME_VERSION_URL = (
    "https://versionhistory.googleapis.com/"
    "v1/chrome/platforms/win/channels/stable/versions"
    "?order_by=version%20desc&page_size=200"
)

EDGE_VERSION_URL = (
    "https://edgeupdates.microsoft.com/"
    "api/products?view=enterprise"
)

FIREFOX_VERSION_URL = (
    "https://product-details.mozilla.org/"
    "1.0/firefox_versions.json"
)

FIREFOX_HISTORY_URL = (
    "https://product-details.mozilla.org/"
    "1.0/firefox_history_stability_releases.json"
)


# ============================================================
# BASIC DOWNLOAD FUNCTIONS
# ============================================================

def download_text(url):

    request = urllib.request.Request(
        url,
        headers={
            "User-Agent":
                "Mozilla/5.0 OS-Support-Dashboard"
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


def download_json(url):

    return json.loads(
        download_text(url)
    )


def get_eol_data(product):

    url = EOL_API.format(
        product=product
    )

    return download_json(url)


# ============================================================
# VERSION HELPERS
# ============================================================

def version_major(version):

    if not version:
        return None

    match = re.match(
        r"^(\d+)",
        str(version)
    )

    if match:

        return int(
            match.group(1)
        )

    return None


def version_tuple(version):

    if not version:
        return tuple()

    numbers = re.findall(
        r"\d+",
        str(version)
    )

    return tuple(
        int(number)
        for number in numbers
    )


def is_supported(item):

    eol = item.get("eol")

    if eol is False or eol is None:
        return True

    if isinstance(eol, str):

        try:

            return (
                date.fromisoformat(eol)
                >=
                date.today()
            )

        except ValueError:

            return False

    return False


# ============================================================
# HTML CLEANING
# ============================================================

def clean_html_text(html):

    text = re.sub(
        r"<script.*?</script>",
        " ",
        html,
        flags=(
            re.IGNORECASE
            |
            re.DOTALL
        )
    )

    text = re.sub(
        r"<style.*?</style>",
        " ",
        text,
        flags=(
            re.IGNORECASE
            |
            re.DOTALL
        )
    )

    text = re.sub(
        r"<[^>]+>",
        " ",
        text
    )

    text = (
        text
        .replace("&nbsp;", " ")
        .replace("&#x27;", "'")
        .replace("&amp;", "&")
    )

    text = re.sub(
        r"\s+",
        " ",
        text
    )

    return text


# ============================================================
# APPLE RELEASE HISTORY
# ============================================================

def get_apple_release_history():

    print(
        "Checking Apple security releases..."
    )

    html = download_text(
        APPLE_SECURITY_URL
    )

    text = clean_html_text(
        html
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


    safari_versions = re.findall(
        r"\bSafari\s+"
        r"(\d+(?:\.\d+){0,2})",
        text,
        flags=re.IGNORECASE
    )


    # Remove duplicates while preserving source order.

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

    safari_versions = list(
        dict.fromkeys(
            safari_versions
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

    print(
        "Apple Safari versions found:",
        safari_versions[:20]
    )


    return {
        "macOS":
            macos_versions,

        "iOS":
            ios_versions,

        "Safari":
            safari_versions,
    }


# ============================================================
# FIND PREVIOUS APPLE MINOR RELEASE
# ============================================================

def find_previous_same_major(
    current_version,
    history
):

    if not current_version:
        return None


    major = version_major(
        current_version
    )


    candidates = [

        version

        for version
        in history

        if (
            version_major(version)
            ==
            major
        )
    ]


    candidates = sorted(
        set(candidates),
        key=version_tuple,
        reverse=True
    )


    try:

        current_index = candidates.index(
            current_version
        )

    except ValueError:

        return None


    if (
        current_index + 1
        <
        len(candidates)
    ):

        return candidates[
            current_index + 1
        ]


    return None


# ============================================================
# FIND PREVIOUS BROWSER MAJOR RELEASE
# ============================================================

def get_previous_major_release(
    versions,
    current_version
):

    current_major = version_major(
        current_version
    )

    if current_major is None:
        return None


    lower_major_versions = [

        version

        for version in versions

        if (
            version_major(version)
            is not None
            and
            version_major(version)
            <
            current_major
        )
    ]


    if not lower_major_versions:
        return None


    previous_major = max(

        version_major(version)

        for version
        in lower_major_versions

        if version_major(version)
        is not None
    )


    candidates = [

        version

        for version
        in lower_major_versions

        if (
            version_major(version)
            ==
            previous_major
        )
    ]


    if not candidates:
        return None


    return max(
        candidates,
        key=version_tuple
    )


# ============================================================
# GOOGLE CHROME
# ============================================================

def get_chrome_data():

    print(
        "Checking Google Chrome..."
    )


    data = download_json(
        CHROME_VERSION_URL
    )


    versions = [

        item.get("version")

        for item
        in data.get(
            "versions",
            []
        )

        if item.get("version")
    ]


    versions = sorted(
        set(versions),
        key=version_tuple,
        reverse=True
    )


    if not versions:

        raise RuntimeError(
            "No Chrome Stable versions found"
        )


    current = versions[0]


    previous = get_previous_major_release(
        versions,
        current
    )


    print(
        "Chrome current:",
        current
    )

    print(
        "Chrome previous major:",
        previous
    )


    return {

        "supported": [
            {
                "version":
                    current
            }
        ],

        "unsupported": (
            [
                {
                    "version":
                        previous
                }
            ]
            if previous
            else []
        )
    }


# ============================================================
# MOZILLA FIREFOX
# ============================================================

def get_firefox_data():

    print(
        "Checking Mozilla Firefox..."
    )


    versions_data = download_json(
        FIREFOX_VERSION_URL
    )


    current = versions_data.get(
        "LATEST_FIREFOX_VERSION"
    )


    if not current:

        raise RuntimeError(
            "LATEST_FIREFOX_VERSION not found"
        )


    history_data = download_json(
        FIREFOX_HISTORY_URL
    )


    history = list(
        history_data.keys()
    )


    previous = get_previous_major_release(
        history,
        current
    )


    print(
        "Firefox current:",
        current
    )

    print(
        "Firefox previous major:",
        previous
    )


    return {

        "supported": [
            {
                "version":
                    current
            }
        ],

        "unsupported": (
            [
                {
                    "version":
                        previous
                }
            ]
            if previous
            else []
        )
    }


# ============================================================
# MICROSOFT EDGE
# ============================================================

def find_edge_stable_versions(data):

    versions = []


    if not isinstance(
        data,
        list
    ):

        return versions


    for product in data:

        if not isinstance(
            product,
            dict
        ):

            continue


        product_name = str(
            product.get(
                "Product",
                ""
            )
        ).lower()


        # Microsoft currently labels the normal
        # production Edge channel as Stable.

        if "stable" not in product_name:
            continue


        releases = product.get(
            "Releases",
            []
        )


        if not isinstance(
            releases,
            list
        ):

            continue


        for release in releases:

            if not isinstance(
                release,
                dict
            ):

                continue


            version = release.get(
                "ProductVersion"
            )


            if version:

                versions.append(
                    str(version)
                )


    return versions


def get_edge_data():

    print(
        "Checking Microsoft Edge..."
    )


    data = download_json(
        EDGE_VERSION_URL
    )


    versions = find_edge_stable_versions(
        data
    )


    versions = sorted(
        set(versions),
        key=version_tuple,
        reverse=True
    )


    if not versions:

        raise RuntimeError(
            "No Microsoft Edge Stable "
            "versions found"
        )


    current = versions[0]


    previous = get_previous_major_release(
        versions,
        current
    )


    print(
        "Edge current:",
        current
    )

    print(
        "Edge previous major:",
        previous
    )


    return {

        "supported": [
            {
                "version":
                    current
            }
        ],

        "unsupported": (
            [
                {
                    "version":
                        previous
                }
            ]
            if previous
            else []
        )
    }


# ============================================================
# APPLE SAFARI
# ============================================================

def get_safari_data(
    apple_history
):

    print(
        "Checking Apple Safari..."
    )


    versions = apple_history.get(
        "Safari",
        []
    )


    versions = [

        version

        for version
        in versions

        if version_major(version)
        is not None
    ]


    versions = sorted(
        set(versions),
        key=version_tuple,
        reverse=True
    )


    if not versions:

        raise RuntimeError(
            "No Safari versions found"
        )


    current = versions[0]


    previous = get_previous_major_release(
        versions,
        current
    )


    print(
        "Safari current:",
        current
    )

    print(
        "Safari previous major:",
        previous
    )


    return {

        "supported": [
            {
                "version":
                    current
            }
        ],

        "unsupported": (
            [
                {
                    "version":
                        previous
                }
            ]
            if previous
            else []
        )
    }


# ============================================================
# READ APPLE HISTORY
# ============================================================

try:

    apple_history = (
        get_apple_release_history()
    )

except Exception as error:

    print(
        "WARNING: Unable to read "
        "Apple security releases:",
        error
    )

    apple_history = {
        "macOS": [],
        "iOS": [],
        "Safari": [],
    }


# ============================================================
# CREATE RESULT
# ============================================================

result = {

    "_last_updated":
        datetime.now(
            timezone.utc
        ).isoformat(),

    "_sources": {

        "endoflife":
            "https://endoflife.date",

        "apple":
            APPLE_SECURITY_URL,

        "chrome":
            CHROME_VERSION_URL,

        "edge":
            EDGE_VERSION_URL,

        "firefox":
            FIREFOX_VERSION_URL,

        "firefox_history":
            FIREFOX_HISTORY_URL,
    },

    "_browsers": {}
}


# ============================================================
# OPERATING SYSTEMS
# ============================================================

for (
    display_name,
    product
) in PRODUCTS.items():

    print(
        f"Checking {display_name}..."
    )


    try:

        releases = get_eol_data(
            product
        )

    except Exception as error:

        print(
            f"ERROR checking "
            f"{display_name}: "
            f"{error}"
        )

        continue


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


        # ----------------------------------------------------
        # Apple minor/security releases
        # ----------------------------------------------------

        if (
            display_name
            in (
                "macOS",
                "iOS"
            )
            and
            latest
        ):

            entry["previous"] = (
                find_previous_same_major(
                    latest,
                    apple_history.get(
                        display_name,
                        []
                    )
                )
            )


        if is_supported(
            release
        ):

            supported.append(
                entry
            )

        else:

            unsupported.append(
                entry
            )


    # Sort releases newest first where possible.

    supported = sorted(
        supported,
        key=lambda item:
            version_tuple(
                item.get(
                    "version",
                    ""
                )
            ),
        reverse=True
    )


    unsupported = sorted(
        unsupported,
        key=lambda item:
            version_tuple(
                item.get(
                    "version",
                    ""
                )
            ),
        reverse=True
    )


    result[
        display_name
    ] = {

        "supported":
            supported,

        "unsupported":
            unsupported[:1],
    }


# ============================================================
# BROWSERS
# ============================================================

browser_functions = {

    "Google Chrome":
        get_chrome_data,

    "Microsoft Edge":
        get_edge_data,

    "Mozilla Firefox":
        get_firefox_data,
}


for (
    browser_name,
    browser_function
) in browser_functions.items():

    try:

        result[
            "_browsers"
        ][
            browser_name
        ] = browser_function()

    except Exception as error:

        print(
            f"ERROR checking "
            f"{browser_name}: "
            f"{error}"
        )


# ============================================================
# SAFARI
# ============================================================

try:

    result[
        "_browsers"
    ][
        "Apple Safari"
    ] = get_safari_data(
        apple_history
    )

except Exception as error:

    print(
        "ERROR checking "
        "Apple Safari:",
        error
    )


# ============================================================
# WRITE JSON
# ============================================================

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


print()
print(
    "os-support.json updated successfully."
)
