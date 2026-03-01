#!/usr/bin/env python3
import json
import time
import random
import os
from datetime import datetime

# --- Asetukset ---
JSON_DIR = './json_data'
os.makedirs(JSON_DIR, exist_ok=True)

BACKUP_FILE = os.path.join(JSON_DIR, 'aircraft_backup.json')
TMP_FILE    = os.path.join(JSON_DIR, 'aircraft_backup.tmp')

PLANE_TTL   = 60        # sekuntia vanhentumiseen
ADD_PROB    = 0.1       # todennäköisyys lisätä uusi kone per sekunti
REMOVE_PROB = 0.3       # todennäköisyys poistaa kone per sekunti

planes = []
next_plane_id = 1
planes_seen = {}  # ICAO -> viimeisin tila (alt, speed, track, lat, lon, rssi)

# --- Oikeat Finnair-koneet testiin ---
finnair_planes = [
    {
        "hex": 0x461EB0,  # ICAO24 hex
        "registration": "OH-LQE",
        "type": "A343",
        "operator": "Finnair",
        "flight": "FIN101",
        "altitude": 35000,
        "speed": 460,
        "track": 90,
        "lat": 60.25,
        "lon": 24.95,
        "rssi": -18.5,
        "last_seen": time.time(),
        "vertical_rate": 0,
        "squawk": 7000,
        "alert": False,
        "on_ground": False
    },
    {
        "hex": 0x461EB1,  # toinen testi-Finnair
        "registration": "OH-LQF",
        "type": "A343",
        "operator": "Finnair",
        "flight": "FIN102",
        "altitude": 33000,
        "speed": 450,
        "track": 80,
        "lat": 60.30,
        "lon": 25.00,
        "rssi": -19.0,
        "last_seen": time.time(),
        "vertical_rate": 0,
        "squawk": 7000,
        "alert": False,
        "on_ground": False
    }
]

# --- Funktio uuden satunnaisen koneen luomiseen ---
def create_plane(pid):
    return {
        "hex": f"TEST{pid:03d}",
        "flight": f"T{pid}",
        "altitude": random.randint(5000, 35000),
        "speed": random.randint(150, 500),
        "track": random.randint(0, 359),
        "lat": 60.0 + random.random(),
        "lon": 24.0 + random.random(),
        "rssi": -10.0 - random.random() * 30,
        "last_seen": time.time()
    }

# --- Lisää aluksi Finnairit ---
for fplane in finnair_planes:
    planes.append(fplane)

# --- Lisää pari satunnaista testikonetta alussa ---
for _ in range(2):
    planes.append(create_plane(next_plane_id))
    next_plane_id += 1

# --- Pääsilmukka ---
while True:
    now = time.time()

    # --- Satunnainen uusi kone ---
    if random.random() < ADD_PROB:
        p = create_plane(next_plane_id)
        planes.append(p)
        print(f"{datetime.now()} Lisätty kone {p['flight']}")
        next_plane_id += 1

    # --- Päivitä olemassa olevien koneiden tiedot ---
    for p in planes:
        # Päivitä satunnaisesti vain TEST-koneita, Finnairit pysyvät pääosin vakiona
        if isinstance(p["hex"], str) and p["hex"].startswith("TEST"):
            p["lat"] += random.uniform(-0.001, 0.001)
            p["lon"] += random.uniform(-0.001, 0.001)
            p["altitude"] += random.randint(-50, 50)
            p["speed"] += random.randint(-5, 5)
            p["track"] = (p["track"] + random.randint(-2, 2)) % 360
            p["rssi"] += random.uniform(-0.5, 0.5)
        p["last_seen"] = now

    # --- Satunnainen poisto vain TEST-koneille ---
    planes_before = len(planes)
    planes = [p for p in planes if not (isinstance(p["hex"], str) and p["hex"].startswith("TEST") and random.random() < REMOVE_PROB)]
    removed = planes_before - len(planes)
    if removed:
        print(f"{datetime.now()} Poistettu {removed} satunnaista konetta")

    # --- TTL:n ylittäneiden poisto ---
    planes_before = len(planes)
    planes = [p for p in planes if now - p["last_seen"] < PLANE_TTL or (isinstance(p["hex"], int))]  # Finnairit pysyvät
    removed_ttl = planes_before - len(planes)
    if removed_ttl:
        print(f"{datetime.now()} Poistettu {removed_ttl} vanhaa konetta TTL:n vuoksi")

    # --- Tulosta uudet ja päivittyneet koneet ---
    for p in planes:
        icao = p["hex"]
        flight = p["flight"]
        current_state = (
            p["altitude"], p["speed"], p["track"],
            p["lat"], p["lon"], p["rssi"]
        )

        if icao not in planes_seen:
            planes_seen[icao] = current_state
            print(f"{datetime.now()} NEW PLANE: ICAO={icao} Flight={flight} "
                  f"Alt={current_state[0]}ft Speed={current_state[1]}kn "
                  f"Hdg={current_state[2]}° Lat={current_state[3]} Lon={current_state[4]} "
                  f"RSSI={current_state[5]}")
        elif planes_seen[icao] != current_state:
            planes_seen[icao] = current_state
            print(f"{datetime.now()} UPDATED: ICAO={icao} Flight={flight} "
                  f"Alt={current_state[0]}ft Speed={current_state[1]}kn "
                  f"Hdg={current_state[2]}° Lat={current_state[3]} Lon={current_state[4]} "
                  f"RSSI={current_state[5]}")

    # --- Kirjoita atomisesti backup-tiedostoon ---
    out_data = {
        "now": now,
        "messages": len(planes),
        "aircraft": planes
    }
    with open(TMP_FILE, "w") as f:
        json.dump(out_data, f, indent=2)
    os.replace(TMP_FILE, BACKUP_FILE)

    time.sleep(1)