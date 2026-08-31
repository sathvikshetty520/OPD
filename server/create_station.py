"""
Provision a new station credential. Run once per device:
    python create_station.py <device_name>

Prints the raw key ONCE -- it is hashed before storage and cannot be
recovered later. Copy it into that device's config.js immediately.
"""

import sys
import secrets
import db
import auth

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python create_station.py <device_name>")
        sys.exit(1)

    device_name = sys.argv[1]
    station_id = "station-" + secrets.token_hex(4)
    raw_key = secrets.token_urlsafe(24)

    db.init_db()
    db.create_station(station_id, auth.hash_password(raw_key), device_name)

    print(f"Station created: {device_name}")
    print(f"  station_id: {station_id}")
    print(f"  STATION_KEY: {raw_key}")
    print()
    print("Copy the STATION_KEY above into that device's config.js now -- it will not be shown again.")