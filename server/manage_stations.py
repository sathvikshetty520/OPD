"""
List or revoke station credentials.
    python manage_stations.py list
    python manage_stations.py revoke <station_id>
"""

import sys
import db

if __name__ == "__main__":
    db.init_db()
    if len(sys.argv) < 2:
        print("Usage: python manage_stations.py list | revoke <station_id>")
        sys.exit(1)

    if sys.argv[1] == "list":
        for s in db.get_all_stations():
            status = "REVOKED" if s["revoked"] else "active"
            print(f"{s['station_id']}  {s['device_name']}  ({status})  created {s['created_at']}")
    elif sys.argv[1] == "revoke" and len(sys.argv) == 3:
        db.revoke_station(sys.argv[2])
        print(f"Revoked: {sys.argv[2]}")
    else:
        print("Usage: python manage_stations.py list | revoke <station_id>")