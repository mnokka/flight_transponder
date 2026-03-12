#!/usr/bin/env python3
import json
import time
import random
import os
from datetime import datetime

# --- ASETUKSET ---
JSON_DIR = "./json_data"
os.makedirs(JSON_DIR, exist_ok=True)

BACKUP_FILE = os.path.join(JSON_DIR, "aircraft_backup.json")
TMP_FILE    = os.path.join(JSON_DIR, "aircraft_backup.tmp")

PLANE_TTL   = 60
ADD_PROB    = 0.15
REMOVE_PROB = 0.2

planes = []
next_plane_id = 1
planes_seen = {}

# ---------------- FINNAIR TESTIKONEET ----------------

finnair_planes = [
{
"hex": "461EB0",
"flight": "FIN101",
"altitude": 35000,
"speed": 460,
"track": 90,
"lat": 60.25,
"lon": 24.95,
"rssi": -18.5,
"vertical_rate": 0,
"squawk": "7000",
"alert": False,
"on_ground": False,
"messages": 100
},
{
"hex": "461EB1",
"flight": "FIN102",
"altitude": 33000,
"speed": 450,
"track": 80,
"lat": 60.30,
"lon": 25.00,
"rssi": -19.0,
"vertical_rate": 0,
"squawk": "7000",
"alert": False,
"on_ground": False,
"messages": 120
}
]

# ---------------- SATUNNAINEN TESTIKONE ----------------

def create_plane(pid):

    hexcode = f"ABC{pid:03X}"

    return {
        "hex": hexcode,
        "flight": f"TST{pid}",
        "altitude": random.randint(5000,35000),
        "speed": random.randint(150,500),
        "track": random.randint(0,359),
        "lat": 60 + random.random(),
        "lon": 24 + random.random(),
        "rssi": -10 - random.random()*30,
        "vertical_rate": random.randint(-1500,1500),
        "squawk": str(random.randint(1000,7777)),
        "alert": False,
        "on_ground": False,
        "messages": random.randint(1,100),
        "last_seen": time.time()
    }

# ---------------- ALKUKONEET ----------------

for p in finnair_planes:
    p["last_seen"] = time.time()
    planes.append(p)

for _ in range(2):
    planes.append(create_plane(next_plane_id))
    next_plane_id += 1

# ---------------- PÄÄLOOPPI ----------------

while True:

    now = time.time()

    # --- uusi kone ---
    if random.random() < ADD_PROB:
        p = create_plane(next_plane_id)
        planes.append(p)
        print(datetime.now(), "NEW", p["flight"])
        next_plane_id += 1

    # --- päivitä koneet ---
    for p in planes:

        if not p["flight"].startswith("FIN"):

            p["lat"] += random.uniform(-0.002,0.002)
            p["lon"] += random.uniform(-0.002,0.002)

            p["altitude"] += random.randint(-100,100)
            p["speed"] += random.randint(-10,10)

            p["track"] = (p["track"] + random.randint(-3,3)) % 360
            p["rssi"] += random.uniform(-0.5,0.5)

        p["messages"] += random.randint(1,10)
        p["last_seen"] = now

    # --- satunnainen poisto ---
    planes = [
        p for p in planes
        if not (
            not p["flight"].startswith("FIN")
            and random.random() < REMOVE_PROB
        )
    ]

    # --- TTL poisto ---
    planes = [
        p for p in planes
        if now - p["last_seen"] < PLANE_TTL or p["flight"].startswith("FIN")
    ]

    # --- debug tuloste ---
    for p in planes:

        icao = p["hex"]

        state = (
            p["altitude"],
            p["speed"],
            p["track"],
            round(p["lat"],5),
            round(p["lon"],5),
            round(p["rssi"],1)
        )

        if icao not in planes_seen:

            planes_seen[icao] = state

            print(datetime.now(),
            "NEW",
            p["flight"],
            state)

        elif planes_seen[icao] != state:

            planes_seen[icao] = state

            print(datetime.now(),
            "UPDATE",
            p["flight"],
            state)

    # --- JSON kirjoitus (atominen) ---
    out = {
        "now": now,
        "messages": len(planes),
        "aircraft": planes
    }

    with open(TMP_FILE, "w") as f:
        json.dump(out, f, indent=2)

    os.replace(TMP_FILE, BACKUP_FILE)

    time.sleep(1)