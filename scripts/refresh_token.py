#!/usr/bin/env python3
"""
Re-generate OAuth token.json for a bot.

Usage:
    python scripts/refresh_token.py leocard
    python scripts/refresh_token.py profcom
    python scripts/refresh_token.py tickets

Opens a browser for Google consent, writes a fresh token.json
into data/<bot>/token.json.

Requirements (install once):
    pip install google-auth google-auth-oauthlib
"""

import json
import sys
from pathlib import Path

from google_auth_oauthlib.flow import InstalledAppFlow

SCOPES = [
    "https://www.googleapis.com/auth/drive",
    "https://www.googleapis.com/auth/spreadsheets",
]

def main():
    if len(sys.argv) < 2 or sys.argv[1] not in ("leocard", "profcom", "tickets"):
        print("Usage: python scripts/refresh_token.py <leocard|profcom|tickets>")
        sys.exit(1)

    bot = sys.argv[1]
    root = Path(__file__).resolve().parent.parent
    creds_file = root / "data" / bot / "credentials.json"
    token_file = root / "data" / bot / "token.json"

    if not creds_file.exists():
        print(f"ERROR: {creds_file} not found")
        sys.exit(1)

    print(f"Authorizing {bot} using {creds_file} ...")
    flow = InstalledAppFlow.from_client_secrets_file(str(creds_file), SCOPES)
    creds = flow.run_local_server(port=0)

    token_file.write_text(creds.to_json())
    token_file.chmod(0o600)
    print(f"Token saved to {token_file}")

    # Show expiry for verification
    data = json.loads(token_file.read_text())
    print(f"  expiry: {data.get('expiry', 'n/a')}")
    print(f"  refresh_token present: {bool(data.get('refresh_token'))}")
    print(f"\nDone. Restart the bot: docker compose restart {bot}")


if __name__ == "__main__":
    main()
