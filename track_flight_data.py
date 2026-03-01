#!/usr/bin/env python3
##########################################################################################
#
# Päivitetty versio: robustimpi vertailu pienille muutoksille
#
##########################################################################################

from datetime import datetime
import sys, subprocess, time, os, json, shutil

heartbeat_interval = 5  # seconds

timestamp = datetime.now().strftime("%d.%m.%Y-%H.%M.%S")

JSON_DIR = "./json_data"
LOG_DIR = "./logs"
log_file = f"{LOG_DIR}/transponder_log_{timestamp}.txt"

AIRCRAFT_FILE = os.path.join(JSON_DIR, "aircraft_backup.json")

os.makedirs(LOG_DIR, exist_ok=True)
os.makedirs(JSON_DIR, exist_ok=True)

print("Used log file:", log_file)

# ==================== JSON-luku ja heartbeat ===================
seen = {}
last_heartbeat = time.time()

def has_changed(old, new, tol=1e-4):
    """Tarkista onko tupleissa merkittäviä muutoksia"""
    for o, n in zip(old, new):
        if isinstance(o, float) and abs(o - n) > tol:
            return True
        if isinstance(o, int) and o != n:
            return True
    return False

print("JSON reading starts!!!!")

try:
    while True:
        if os.path.exists(AIRCRAFT_FILE):
            try:
                with open(AIRCRAFT_FILE, "r") as f:
                    data = json.load(f)
                planes = data.get("aircraft", [])
            except json.JSONDecodeError:
                planes = []
                print("DEBUG: JSON decode error, retrying...")
                time.sleep(0.1)
                continue
        else:
            planes = []

        now = time.time()

        if not planes and now - last_heartbeat >= heartbeat_interval:
            print(f"{datetime.now()} Ohjelma toimii, ei havaintoja")
            last_heartbeat = now

        for p in planes:
            icao = p.get("hex", "?")
            flight = p.get("flight", "?")
            # Pyöristetään float-arvot vertailua varten
            current_state = (
                round(p.get("altitude", 0), 0),
                round(p.get("speed", 0), 0),
                round(p.get("track", 0), 0),
                round(p.get("lat", 5), 5),
                round(p.get("lon", 5), 5),
                round(p.get("rssi", 0.0), 1),
            )

            if icao not in seen:
                seen[icao] = current_state
                print(f"{datetime.now()} NEW PLANE: ICAO={icao} Flight={flight} "
                      f"Alt={current_state[0]}ft Speed={current_state[1]}kn "
                      f"Hdg={current_state[2]}° Lat={current_state[3]} Lon={current_state[4]} "
                      f"RSSI={current_state[5]}")
            elif has_changed(seen[icao], current_state):
                seen[icao] = current_state
                print(f"{datetime.now()} UPDATED: ICAO={icao} Flight={flight} "
                      f"Alt={current_state[0]}ft Speed={current_state[1]}kn "
                      f"Hdg={current_state[2]}° Lat={current_state[3]} Lon={current_state[4]} "
                      f"RSSI={current_state[5]}")

        time.sleep(1)

except KeyboardInterrupt:
    print("\nLopetetaan ohjelma...")