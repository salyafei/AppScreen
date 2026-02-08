#!/usr/bin/env python3
"""
App Store Connect - Screenshot Upload & App Metadata Manager

This script:
1. Authenticates with App Store Connect API using your .p8 key
2. Lists your apps or creates a new app listing
3. Uploads mock screenshots for all required device sizes
4. Fills in app descriptions, keywords, and metadata

Requirements:
    pip install PyJWT[crypto] requests

Usage:
    python3 deploy_to_appstore.py --list-apps
    python3 deploy_to_appstore.py --app-id <APP_ID> --upload-screenshots
    python3 deploy_to_appstore.py --app-id <APP_ID> --update-metadata
    python3 deploy_to_appstore.py --app-id <APP_ID> --full-setup
"""

import argparse
import hashlib
import json
import os
import struct
import sys
import time
from pathlib import Path

try:
    import jwt
    import requests
except ImportError:
    print("Missing dependencies. Install with:")
    print("  pip install PyJWT[crypto] requests")
    sys.exit(1)

# ─── Configuration ───────────────────────────────────────────────────────────

ISSUER_ID = "3e37f591-3b45-4897-bf75-ebdd8fcd53a3"
KEY_ID = "6GFT6H55RC"
KEY_FILE = os.path.join(os.path.dirname(__file__), "AuthKey_6GFT6H55RC.p8")
BASE_URL = "https://api.appstoreconnect.apple.com/v1"

# App metadata defaults (customize these for your app)
APP_METADATA = {
    "en-US": {
        "name": "App Screenshot Generator",
        "subtitle": "Create Professional Store Screenshots",
        "description": (
            "App Screenshot Generator helps you create stunning, professional "
            "app store screenshots for both iOS and Android platforms.\n\n"
            "KEY FEATURES:\n"
            "- Support for all iPhone and iPad screen sizes\n"
            "- Android phone and tablet support\n"
            "- Beautiful gradient backgrounds with preset colors\n"
            "- Custom caption text with adjustable size and position\n"
            "- Realistic device frames with notch rendering\n"
            "- Image rotation (0, 90, 180, 270 degrees)\n"
            "- Interactive image cropping tool\n"
            "- Decorative frame styles (thin, thick, shadow, double, glow)\n"
            "- Batch download for multiple device sizes\n"
            "- Real-time preview as you customize\n\n"
            "SUPPORTED DEVICES:\n"
            "- iPhone 6.9\", 6.7\", 6.5\", 5.5\"\n"
            "- iPhone 16 Pro Max\n"
            "- iPad 13\", 12.9\", 11\"\n"
            "- Android Phone & Tablet\n\n"
            "Create professional marketing assets for your app in minutes. "
            "Upload your screenshot, choose a background, add a caption, "
            "and download store-ready images instantly."
        ),
        "keywords": "screenshot,app store,mockup,device frame,marketing,design,generator,ios,android,preview",
        "promotionalText": "Create beautiful app store screenshots in seconds!",
        "whatsNew": "New features: Image rotation, interactive cropping, decorative frame styles, and improved fit-to-preview scaling.",
        "supportUrl": "https://github.com/salyafei/AppScreen",
        "marketingUrl": "https://salyafei.github.io/AppScreen/",
    }
}

# Screenshot display targets mapped to App Store Connect display types
# See: https://developer.apple.com/help/app-store-connect/reference/screenshot-specifications
SCREENSHOT_DISPLAY_TYPES = {
    "iphone-6.9": "APP_IPHONE_67",
    "iphone-6.7": "APP_IPHONE_67",
    "iphone-6.5": "APP_IPHONE_65",
    "iphone-5.5": "APP_IPHONE_55",
    "ipad-13": "APP_IPAD_PRO_3GEN_129",
    "ipad-12.9": "APP_IPAD_PRO_129",
}


# ─── Authentication ──────────────────────────────────────────────────────────

def get_token():
    """Generate a JWT for App Store Connect API authentication."""
    with open(KEY_FILE, "r") as f:
        private_key = f.read()

    now = int(time.time())
    payload = {
        "iss": ISSUER_ID,
        "iat": now,
        "exp": now + 1200,  # 20 minutes
        "aud": "appstoreconnect-v1",
    }
    headers_data = {"alg": "ES256", "kid": KEY_ID, "typ": "JWT"}
    return jwt.encode(payload, private_key, algorithm="ES256", headers=headers_data)


def api_headers():
    """Return headers for API requests."""
    return {
        "Authorization": f"Bearer {get_token()}",
        "Content-Type": "application/json",
    }


# ─── API Helpers ─────────────────────────────────────────────────────────────

def api_get(path, params=None):
    """Make a GET request to the App Store Connect API."""
    url = f"{BASE_URL}/{path}"
    resp = requests.get(url, headers=api_headers(), params=params)
    resp.raise_for_status()
    return resp.json()


def api_post(path, data):
    """Make a POST request to the App Store Connect API."""
    url = f"{BASE_URL}/{path}"
    resp = requests.post(url, headers=api_headers(), json=data)
    if not resp.ok:
        print(f"  Error {resp.status_code}: {resp.text}")
    resp.raise_for_status()
    return resp.json()


def api_patch(path, data):
    """Make a PATCH request to the App Store Connect API."""
    url = f"{BASE_URL}/{path}"
    resp = requests.patch(url, headers=api_headers(), json=data)
    if not resp.ok:
        print(f"  Error {resp.status_code}: {resp.text}")
    resp.raise_for_status()
    return resp.json()


def api_delete(path):
    """Make a DELETE request to the App Store Connect API."""
    url = f"{BASE_URL}/{path}"
    resp = requests.delete(url, headers=api_headers())
    resp.raise_for_status()


# ─── App Listing ─────────────────────────────────────────────────────────────

def list_apps():
    """List all apps in your App Store Connect account."""
    data = api_get("apps", params={"fields[apps]": "name,bundleId,sku,primaryLocale"})
    apps = data.get("data", [])

    if not apps:
        print("No apps found in your App Store Connect account.")
        print("\nTo create an app, you need to:")
        print("  1. Register a Bundle ID in the Apple Developer portal")
        print("  2. Run: python3 deploy_to_appstore.py --create-app --bundle-id <your.bundle.id>")
        return

    print(f"Found {len(apps)} app(s):\n")
    for app in apps:
        attrs = app["attributes"]
        print(f"  ID: {app['id']}")
        print(f"  Name: {attrs.get('name', 'N/A')}")
        print(f"  Bundle ID: {attrs.get('bundleId', 'N/A')}")
        print(f"  SKU: {attrs.get('sku', 'N/A')}")
        print()


def get_app_store_version(app_id):
    """Get the editable App Store version for an app."""
    data = api_get(
        f"apps/{app_id}/appStoreVersions",
        params={
            "filter[appStoreState]": "PREPARE_FOR_SUBMISSION,DEVELOPER_REJECTED,REJECTED,METADATA_REJECTED,WAITING_FOR_REVIEW,IN_REVIEW,PENDING_DEVELOPER_RELEASE,READY_FOR_SALE",
            "fields[appStoreVersions]": "versionString,appStoreState,platform",
        },
    )
    versions = data.get("data", [])

    # Prefer an editable version
    for v in versions:
        if v["attributes"]["appStoreState"] in ("PREPARE_FOR_SUBMISSION", "DEVELOPER_REJECTED", "REJECTED", "METADATA_REJECTED"):
            return v

    # Return the latest version otherwise
    return versions[0] if versions else None


def create_app_store_version(app_id, version_string="1.0"):
    """Create a new App Store version for submission."""
    data = api_post("appStoreVersions", {
        "data": {
            "type": "appStoreVersions",
            "attributes": {
                "platform": "IOS",
                "versionString": version_string,
            },
            "relationships": {
                "app": {
                    "data": {"type": "apps", "id": app_id}
                }
            }
        }
    })
    return data["data"]


# ─── Metadata ────────────────────────────────────────────────────────────────

def update_app_info(app_id):
    """Update app-level info (subtitle, categories)."""
    # Get app info localizations
    data = api_get(f"apps/{app_id}/appInfos")
    app_infos = data.get("data", [])

    if not app_infos:
        print("  No app info records found.")
        return

    app_info_id = app_infos[0]["id"]

    # Get existing localizations
    loc_data = api_get(f"appInfos/{app_info_id}/appInfoLocalizations")
    localizations = loc_data.get("data", [])

    for locale, meta in APP_METADATA.items():
        existing = next((l for l in localizations if l["attributes"]["locale"] == locale), None)

        if existing:
            print(f"  Updating app info for {locale}...")
            api_patch(f"appInfoLocalizations/{existing['id']}", {
                "data": {
                    "type": "appInfoLocalizations",
                    "id": existing["id"],
                    "attributes": {
                        "name": meta["name"],
                        "subtitle": meta["subtitle"],
                    }
                }
            })
        else:
            print(f"  Creating app info localization for {locale}...")
            api_post("appInfoLocalizations", {
                "data": {
                    "type": "appInfoLocalizations",
                    "attributes": {
                        "locale": locale,
                        "name": meta["name"],
                        "subtitle": meta["subtitle"],
                    },
                    "relationships": {
                        "appInfo": {"data": {"type": "appInfos", "id": app_info_id}}
                    }
                }
            })


def update_version_metadata(version_id):
    """Update version-level metadata (description, keywords, whatsNew, etc.)."""
    # Get existing localizations
    loc_data = api_get(f"appStoreVersions/{version_id}/appStoreVersionLocalizations")
    localizations = loc_data.get("data", [])

    for locale, meta in APP_METADATA.items():
        existing = next((l for l in localizations if l["attributes"]["locale"] == locale), None)

        attrs = {
            "description": meta["description"],
            "keywords": meta["keywords"],
            "promotionalText": meta["promotionalText"],
            "whatsNew": meta["whatsNew"],
            "supportUrl": meta["supportUrl"],
            "marketingUrl": meta["marketingUrl"],
        }

        if existing:
            print(f"  Updating version metadata for {locale}...")
            api_patch(f"appStoreVersionLocalizations/{existing['id']}", {
                "data": {
                    "type": "appStoreVersionLocalizations",
                    "id": existing["id"],
                    "attributes": attrs,
                }
            })
        else:
            print(f"  Creating version localization for {locale}...")
            attrs["locale"] = locale
            api_post("appStoreVersionLocalizations", {
                "data": {
                    "type": "appStoreVersionLocalizations",
                    "attributes": attrs,
                    "relationships": {
                        "appStoreVersion": {"data": {"type": "appStoreVersions", "id": version_id}}
                    }
                }
            })


# ─── Screenshots ─────────────────────────────────────────────────────────────

def upload_screenshot(localization_id, display_type, image_path):
    """Upload a screenshot to App Store Connect using the 3-step process."""
    file_size = os.path.getsize(image_path)
    file_name = os.path.basename(image_path)

    print(f"    Uploading {file_name} ({display_type})...")

    # Step 1: Reserve the screenshot
    reserve_data = api_post("appScreenshots", {
        "data": {
            "type": "appScreenshots",
            "attributes": {
                "fileName": file_name,
                "fileSize": file_size,
            },
            "relationships": {
                "appScreenshotSet": {
                    "data": {"type": "appScreenshotSets", "id": localization_id}
                }
            }
        }
    })

    screenshot = reserve_data["data"]
    screenshot_id = screenshot["id"]
    upload_ops = screenshot["attributes"].get("uploadOperations", [])

    if not upload_ops:
        print(f"    No upload operations returned for {file_name}")
        return

    # Step 2: Upload the file parts
    with open(image_path, "rb") as f:
        file_data = f.read()

    for op in upload_ops:
        url = op["url"]
        op_headers = {h["name"]: h["value"] for h in op["requestHeaders"]}
        offset = op["offset"]
        length = op["length"]
        chunk = file_data[offset:offset + length]

        resp = requests.put(url, headers=op_headers, data=chunk)
        resp.raise_for_status()

    # Step 3: Commit the upload
    md5 = hashlib.md5(file_data).digest()
    source_file_checksum = md5.hex()

    api_patch(f"appScreenshots/{screenshot_id}", {
        "data": {
            "type": "appScreenshots",
            "id": screenshot_id,
            "attributes": {
                "uploaded": True,
                "sourceFileChecksum": source_file_checksum,
            }
        }
    })

    print(f"    Uploaded {file_name} successfully!")


def upload_screenshots(version_id, screenshots_dir):
    """Upload all screenshots for a version."""
    # Get version localizations
    loc_data = api_get(f"appStoreVersions/{version_id}/appStoreVersionLocalizations")
    localizations = loc_data.get("data", [])

    if not localizations:
        print("  No localizations found. Creating en-US...")
        loc_resp = api_post("appStoreVersionLocalizations", {
            "data": {
                "type": "appStoreVersionLocalizations",
                "attributes": {"locale": "en-US"},
                "relationships": {
                    "appStoreVersion": {"data": {"type": "appStoreVersions", "id": version_id}}
                }
            }
        })
        localizations = [loc_resp["data"]]

    en_loc = next((l for l in localizations if l["attributes"]["locale"] == "en-US"), localizations[0])
    loc_id = en_loc["id"]

    # Get or create screenshot sets for each display type
    sets_data = api_get(f"appStoreVersionLocalizations/{loc_id}/appScreenshotSets")
    existing_sets = {s["attributes"]["screenshotDisplayType"]: s["id"] for s in sets_data.get("data", [])}

    screenshots_dir = Path(screenshots_dir)
    screenshot_files = sorted(screenshots_dir.glob("*.png"))

    if not screenshot_files:
        print(f"  No PNG files found in {screenshots_dir}")
        print(f"  Generate screenshots first using the web app or the mock-screenshot.png")
        return

    for display_type in SCREENSHOT_DISPLAY_TYPES.values():
        # Create screenshot set if it doesn't exist
        if display_type not in existing_sets:
            print(f"  Creating screenshot set for {display_type}...")
            set_resp = api_post("appScreenshotSets", {
                "data": {
                    "type": "appScreenshotSets",
                    "attributes": {"screenshotDisplayType": display_type},
                    "relationships": {
                        "appStoreVersionLocalization": {"data": {"type": "appStoreVersionLocalizations", "id": loc_id}}
                    }
                }
            })
            set_id = set_resp["data"]["id"]
        else:
            set_id = existing_sets[display_type]

        # Upload screenshots for this display type
        for screenshot_file in screenshot_files:
            upload_screenshot(set_id, display_type, str(screenshot_file))


# ─── Generate Screenshots ───────────────────────────────────────────────────

def generate_mock_screenshots(output_dir):
    """Generate mock screenshots for all required device sizes using the existing mock."""
    from PIL import Image

    output_dir = Path(output_dir)
    output_dir.mkdir(exist_ok=True)

    mock_path = Path(__file__).parent / "mock-screenshot.png"
    if not mock_path.exists():
        print(f"  Mock screenshot not found at {mock_path}")
        return

    mock_img = Image.open(mock_path)
    print(f"  Source mock: {mock_img.size[0]}x{mock_img.size[1]}")

    device_sizes = {
        "iphone-6.9": (1320, 2868),
        "iphone-6.7": (1290, 2796),
        "iphone-6.5": (1284, 2778),
        "iphone-5.5": (1242, 2208),
        "ipad-13": (2064, 2752),
        "ipad-12.9": (2048, 2732),
    }

    for device_name, (w, h) in device_sizes.items():
        output_path = output_dir / f"screenshot_{device_name}_{w}x{h}.png"
        resized = mock_img.resize((w, h), Image.LANCZOS)
        resized.save(str(output_path), "PNG")
        print(f"  Generated: {output_path.name} ({w}x{h})")

    print(f"\n  {len(device_sizes)} screenshots generated in {output_dir}/")


# ─── Main ────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="App Store Connect Screenshot & Metadata Manager")
    parser.add_argument("--list-apps", action="store_true", help="List all apps in your account")
    parser.add_argument("--app-id", help="App ID to operate on")
    parser.add_argument("--upload-screenshots", action="store_true", help="Upload screenshots for the app")
    parser.add_argument("--update-metadata", action="store_true", help="Update app descriptions and metadata")
    parser.add_argument("--full-setup", action="store_true", help="Do everything: metadata + screenshots")
    parser.add_argument("--generate-screenshots", action="store_true", help="Generate resized mock screenshots for all device sizes")
    parser.add_argument("--screenshots-dir", default="./screenshots", help="Directory containing/storing screenshots (default: ./screenshots)")
    parser.add_argument("--version", default=None, help="App version string (default: use existing or create 1.0)")

    args = parser.parse_args()

    if not os.path.exists(KEY_FILE):
        print(f"Error: Key file not found at {KEY_FILE}")
        sys.exit(1)

    # Test auth
    print("Authenticating with App Store Connect...")
    try:
        token = get_token()
        print("  JWT generated successfully.\n")
    except Exception as e:
        print(f"  Authentication failed: {e}")
        sys.exit(1)

    if args.list_apps:
        list_apps()
        return

    if args.generate_screenshots:
        print("Generating mock screenshots for all device sizes...")
        generate_mock_screenshots(args.screenshots_dir)
        return

    if not args.app_id:
        print("Error: --app-id is required for this operation.")
        print("Run with --list-apps first to find your app ID.")
        sys.exit(1)

    if args.full_setup or args.update_metadata:
        print("Updating app metadata...")
        update_app_info(args.app_id)

        version = get_app_store_version(args.app_id)
        if not version:
            ver_string = args.version or "1.0"
            print(f"  No editable version found. Creating v{ver_string}...")
            version = create_app_store_version(args.app_id, ver_string)

        print(f"  Version: {version['attributes']['versionString']} ({version['attributes']['appStoreState']})")
        update_version_metadata(version["id"])
        print("  Metadata updated!\n")

    if args.full_setup or args.upload_screenshots:
        version = get_app_store_version(args.app_id)
        if not version:
            ver_string = args.version or "1.0"
            print(f"  No editable version found. Creating v{ver_string}...")
            version = create_app_store_version(args.app_id, ver_string)

        screenshots_dir = Path(args.screenshots_dir)
        if not screenshots_dir.exists() or not list(screenshots_dir.glob("*.png")):
            print(f"  No screenshots found in {screenshots_dir}. Generating...")
            generate_mock_screenshots(args.screenshots_dir)

        print("Uploading screenshots...")
        upload_screenshots(version["id"], args.screenshots_dir)
        print("  Screenshots uploaded!\n")

    print("Done!")


if __name__ == "__main__":
    main()
