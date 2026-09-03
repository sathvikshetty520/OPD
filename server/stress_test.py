"""
Basic load test: fires N concurrent case submissions at the server and
reports success/failure counts and timing.

Usage:
    python stress_test.py <server_url> <station_key> [num_requests]

Example:
    python stress_test.py https://192.168.1.102:5000 your-real-station-key 50
"""
import sys
import time
import uuid
import json
import concurrent.futures
import urllib.request
import urllib.error
import ssl


def submit_case(base_url, station_key, i):
    payload = {
        "case_id": str(uuid.uuid4()),
        "patient_token": f"LOAD-TEST-{i}",
        "tier": "standard",
        "tier_label": "Standard",
        "department": "General medicine",
        "matched_rules": ["load test synthetic case"],
        "escalate": False,
        "protocol_version": "0.1.0",
        "timestamp": "2026-08-30T12:00:00Z",
        "status": "routed",
    }
    req = urllib.request.Request(
        f"{base_url}/api/cases",
        data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json", "X-Station-Key": station_key},
        method="POST",
    )
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE  # self-signed cert -- skip verification for this test tool
    start = time.time()
    try:
        with urllib.request.urlopen(req, timeout=10, context=ctx) as resp:
            return resp.status, time.time() - start
    except urllib.error.HTTPError as e:
        return e.code, time.time() - start
    except Exception as e:
        return None, time.time() - start


if __name__ == "__main__":
    base_url = sys.argv[1]
    station_key = sys.argv[2]
    n = int(sys.argv[3]) if len(sys.argv) > 3 else 50

    print(f"Firing {n} concurrent submissions at {base_url} ...")
    results = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=20) as ex:
        futures = [ex.submit(submit_case, base_url, station_key, i) for i in range(n)]
        for f in concurrent.futures.as_completed(futures):
            results.append(f.result())

    ok = sum(1 for status, _ in results if status == 201)
    failed = n - ok
    times = [t for _, t in results]
    print(f"Success: {ok}/{n}")
    print(f"Failed:  {failed}/{n}")
    print(f"Avg response time: {sum(times)/len(times):.3f}s")
    print(f"Max response time: {max(times):.3f}s")