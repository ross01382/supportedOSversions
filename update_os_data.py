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


EOL_API = (
    "https://endoflife.date/api/{product}.json"
)

APPLE_SECURITY_URL = (
    "https://support.apple.com/en-us/100100"
)

CHROME_VERSION_URL = (
    "https://versionhistory.googleapis.com/"
    "v1/chrome/platforms/win/channels/stable/versions"
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
        download_text(
            url
        )
    )


def get_eol_data(product):

    url = EOL_API.format(
        product=product
    )

    return download_json(
        url
    )


def is_supported(item):

    eol = item.get(
        "eol"
    )

    if (
        eol is False
        or
        eol is None
    ):

        return True


    if isinstance(
        eol,
        str
    ):

        try:

            return (
                date.fromisoformat(
                    eol
                )
                >=
                date.today()
            )

        except ValueError:

            return False


    return False


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
        .replace(
            "&nbsp;",
            " "
        )
        .replace(
            "&#x27;",
            "'"
        )
        .replace(
            "&amp;",
            "&"
        )
    )

    text = re.sub(
        r"\s+",
        " ",
        text
    )

    return text


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
            version_major(
                version
            )
            ==
            major
        )
    ]


    candidates = sorted(
        set(
            candidates
        ),
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
        len(
            candidates
        )
    ):

        return candidates[
            current_index + 1
        ]


    return None


def get_previous_major_release(
    versions,
    current_version
):

    current_major = version_major(
        current_version
    )


    if current_major is None:

        return None


    previous_major = (
        current_major
        -
        1
    )


    candidates = [

        version

        for version
        in versions

        if (
            version_major(
                version
            )
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


# -------------------------------------------------
# Chrome
# -------------------------------------------------

def get_chrome_data():

    print(
        "Checking Google Chrome..."
    )


    data = download_json(
        CHROME_VERSION_URL
    )


    versions = [

        item.get(
            "version"
        )

        for item
        in data.get(
            "versions",
            []
        )

        if item.get(
            "version"
        )
    ]


    versions = sorted(
        set(
            versions
        ),
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


# -------------------------------------------------
# Firefox
# -------------------------------------------------

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


# -------------------------------------------------
# Microsoft Edge
# -------------------------------------------------

def find_edge_stable_versions(data):

    versions = []


    if not isinstance(
        data,
        list
    ):

        return versions


    for product in data:

        product_name = str(
            product.get(
                "Product",
                ""
            )
        ).lower()


        if (
            "stable"
            not in product_name
        ):

            continue


        for release in product.get(
            "Releases",
            []
        ):

            version = release.get(
                "ProductVersion"
            )


            if version:

                versions.append(
                    version
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
        set(
            versions
        ),
        key=version_tuple,
        reverse=True
    )


    if not versions:

        raise RuntimeError(
            "No Microsoft Edge Stable versions found"
        )


    current = versions[0]


    previous = get_previous_major_release(
        versions,
        current
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


# -------------------------------------------------
# Safari
# -------------------------------------------------

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


    versions = sorted(
        set(
            versions
        ),
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


# -------------------------------------------------
# Apple history
# -------------------------------------------------

try:

    apple_history = (
        get_apple_release_history()
    )

except Exception as error:

    print(
        "Warning: Unable to read "
        "Apple security releases:",
        error
    )

    apple_history = {
        "macOS": [],
        "iOS": [],
        "Safari": [],
    }


# -------------------------------------------------
# Main result
# -------------------------------------------------

result = {

    "_last_updated":
        datetime.now(
            timezone.utc
        ).isoformat(),

    "_sources": {

        "support":
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


# -------------------------------------------------
# Operating systems
# -------------------------------------------------

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


    /*
    Python does not support C-style comments.
    This marker is intentionally not valid and
    must not appear in the final file.
    */
