import json
import time
from datetime import datetime
import os

JSON_DIR = './json_data'
HEARTBEAT_INTERVAL = 60
seen = set()
last_heartbeat = time.time()

while True:
    aircraft_file = os.path.join(JSON_DIR, 'aircraft.json')
    if os.path.exists(aircraft_file):
        with open(aircraft_file, 'r') as f:
            data = json.load(f)
            planes = data.get("aircraft", [])

            now = time.time()
            if not planes and now - last_heartbeat >= HEARTBEAT_INTERVAL:
                print(f"{datetime.now()} Ohjelma toimii, ei havaintoja")
                last_heartbeat = now

            for p in planes:
                icao = p.get("hex", "?")
                flight = p.get("flight", "?")
                alt = p.get("altitude", "?")
                spd = p.get("speed", "?")
                hdg = p.get("track", "?")
                lat = p.get("lat", "?")
                lon = p.get("lon", "?")
                rssi = p.get("rssi", "?")

                if icao not in seen:
                    seen.add(icao)
                    print(f"{datetime.now()} Uusi kone: ICAO={icao} Flight={flight} Alt={alt}ft "
                          f"Speed={spd}kn Hdg={hdg}° Lat={lat} Lon={lon} RSSI={rssi}")

    time.sleep(1)