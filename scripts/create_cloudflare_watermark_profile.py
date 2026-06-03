"""
Temporary one-off script — create a Cloudflare Stream watermark profile.

Usage:
    python scripts/create_cloudflare_watermark_profile.py [--watermark-path PATH]

The script:
  - reads credentials from .env (never prints them)
  - uploads watermark.png to the Cloudflare Stream watermarks API
  - prints only the returned watermark UID
  - never writes secrets to stdout/files
"""

import argparse
import os
import sys
from pathlib import Path

import requests
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")

ACCOUNT_ID = os.getenv("CLOUDFLARE_ACCOUNT_ID", "")
API_TOKEN = os.getenv("CLOUDFLARE_STREAM_API_TOKEN", "")

WATERMARK_NAME = "Kata Dejanovic Photography Watermark"
OPACITY = "0.50"
PADDING = "0.03"
SCALE = "0.36"
POSITION = "lowerRight"


def create_watermark(watermark_path: Path) -> str:
    if not ACCOUNT_ID:
        sys.exit("ERROR: CLOUDFLARE_ACCOUNT_ID is not set in .env")
    if not API_TOKEN:
        sys.exit("ERROR: CLOUDFLARE_STREAM_API_TOKEN is not set in .env")
    if not watermark_path.is_file():
        sys.exit(f"ERROR: watermark file not found: {watermark_path}")

    url = f"https://api.cloudflare.com/client/v4/accounts/{ACCOUNT_ID}/stream/watermarks"
    headers = {"Authorization": f"Bearer {API_TOKEN}"}
    data = {
        "name": WATERMARK_NAME,
        "opacity": OPACITY,
        "padding": PADDING,
        "scale": SCALE,
        "position": POSITION,
    }

    with open(watermark_path, "rb") as f:
        files = {"file": (watermark_path.name, f, "image/png")}
        response = requests.post(url, headers=headers, data=data, files=files)

    if not response.ok:
        sys.exit(f"ERROR: Cloudflare API returned {response.status_code}: {response.text}")

    payload = response.json()
    if not payload.get("success"):
        sys.exit(f"ERROR: API call unsuccessful: {payload.get('errors')}")

    uid = payload["result"]["uid"]
    return uid


def list_watermarks() -> list:
    url = f"https://api.cloudflare.com/client/v4/accounts/{ACCOUNT_ID}/stream/watermarks"
    headers = {"Authorization": f"Bearer {API_TOKEN}"}
    response = requests.get(url, headers=headers)
    if not response.ok:
        sys.exit(f"ERROR: validation GET returned {response.status_code}: {response.text}")
    return response.json().get("result", [])


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--watermark-path",
        default=str(Path.home() / "Downloads" / "watermark.png"),
        help="Path to the watermark PNG file",
    )
    args = parser.parse_args()
    watermark_path = Path(args.watermark_path)

    print(f"Creating watermark profile from: {watermark_path}")
    uid = create_watermark(watermark_path)
    print(f"SUCCESS — Watermark UID: {uid}")

    print("Validating — listing existing watermark profiles...")
    profiles = list_watermarks()
    uids = [p.get("uid") for p in profiles]
    if uid in uids:
        print(f"VALIDATION PASSED — UID {uid} confirmed in watermark list.")
    else:
        print(f"WARNING — UID {uid} not found in watermark list response.")

    print(f"\nAdd this to your .env:\nCLOUDFLARE_STREAM_WATERMARK_UID={uid}")


if __name__ == "__main__":
    main()
