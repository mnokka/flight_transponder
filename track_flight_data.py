#!/usr/bin/env python3
##########################################################################################
#
# Author: mika.nokka1@gmail.com February 2026
#

from datetime import datetime
import sys, subprocess, time, os, json

heartbeat_interval = 5  # seconds

timestamp = datetime.now().strftime("%d.%m.%Y-%H.%M.%S")

JSON_DIR = "./json_data"
LOG_DIR = "./logs"
log_file = f"{LOG_DIR}/transponder_log_{timestamp}.txt"
AIRCRAFT_FILE = os.path.join(JSON_DIR, "aircraft_backup.json")

# Luo hakemistot, jos puuttuvat
os.makedirs(LOG_DIR, exist_ok=True)
os.makedirs(JSON_DIR, exist_ok=True)

print("Used log file:", log_file)

# ==================== Käynnistä dump1090 ===================
print("Käynnistetään dump1090-mutability...")
log_write = open(log_file, "a", buffering=1)

proc = subprocess.Popen(
    [
        'dump1090-mutability',
        '--freq', '1090000000',
        '--gain', '49.6',
        '--net',                # verkko on päällä, mutta HTTP ei toimi
        '--write-json', JSON_DIR,
        '--write-json-every', '1'
    ],
    stdout=log_write,
    stderr=log_write
)

# ==================== Lue startup-viestit ===================
print("------ dump1090-mutability start messages ------")
with open(log_file, "r") as log_reader:
    log_reader.seek(0.0)
    start_time = time.time()
    while time.time() - start_time < 6:
        line = log_reader.readline()
        if not line:
            time.sleep(0.2)
            continue
        line = line.strip()
        print("STARTUP MESSAGE:", line)

print("Start messages read, program starting operations")

# ==================== JSON-luku ja heartbeat ===================
seen = {}
last_heartbeat = time.time()

print("JSON reading starts!!!!")

try:
    while True:
        if os.path.exists(AIRCRAFT_FILE):
            with open(AIRCRAFT_FILE, "r") as f:
                try:
                    data = json.load(f)
                    planes = data.get("aircraft", [])
                    #print("DATA:",data)
                except json.JSONDecodeError:
                    planes = []
                    print("DEBUG: JSON decode error")

            now = time.time()

            # Heartbeat, jos ei koneita
            if not planes and now - last_heartbeat >= heartbeat_interval:
                print(f"{datetime.now()} Ohjelma toimii, ei havaintoja")
                last_heartbeat = now

            # Uusien koneiden tulostus
            for p in planes:
                icao = p.get("hex", "?")
                flight = p.get("flight", "?")
                #alt = p.get("altitude", "?")
                #spd = p.get("speed", "?")
                #hdg = p.get("track", "?")
                #lat = p.get("lat", "?")
                #lon = p.get("lon", "?")
                #rssi = p.get("rssi", "?")
                current_state = (p.get("altitude"), p.get("speed"), p.get("track"),
                     p.get("lat"), p.get("lon"), p.get("rssi"))

                if icao not in seen:
                    seen[icao] = current_state
                    print(f"{datetime.now()} NEW PLANE: ICAO={icao} Flight={flight} "
                        f"Alt={current_state[0]}ft Speed={current_state[1]}kn "
                        f"Hdg={current_state[2]}° Lat={current_state[3]} Lon={current_state[4]} "
                        f"RSSI={current_state[5]}")
                else:
                    # Tarkista onko jokin muuttunut
                    if seen[icao] != current_state:
                        seen[icao] = current_state
                        print(f"{datetime.now()} UPDATED: ICAO={icao} Flight={flight} "
                            f"Alt={current_state[0]}ft Speed={current_state[1]}kn "
                            f"Hdg={current_state[2]}° Lat={current_state[3]} Lon={current_state[4]} "
                            f"RSSI={current_state[5]}")
        time.sleep(1)

except KeyboardInterrupt:
    print("\nLopetetaan ohjelma...")
    proc.terminate()
    proc.wait()