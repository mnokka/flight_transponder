#!/usr/bin/env python3
import json
import time
from datetime import datetime
import random
import os

JSON_DIR = './json_data'
os.makedirs(JSON_DIR, exist_ok=True)

JSON_FILE = os.path.join(JSON_DIR, 'aircraft_backup.json')
TMP_FILE  = os.path.join(JSON_DIR, 'aircraft_backup.tmp')

PLANE_TTL = 60      # sekuntia, jonka jälkeen kone katoaa
ADD_INTERVAL = 30  # uusi kone 30 s välein

planes = []
next_plane_id = 1
last_add_time = 0

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

# lisää heti aloituskoneet
for _ in range(2):
    planes.append(create_plane(next_plane_id))
    next_plane_id += 1

while True:
    now = time.time()

    # ---- lisää uusi kone ----
    if now - last_add_time >= ADD_INTERVAL:
        p = create_plane(next_plane_id)
        planes.append(p)
        print(f"{datetime.now()} Lisätty kone {p['flight']}")
        next_plane_id += 1
        last_add_time = now

    # ---- päivitä koneet ----
    for p in planes:
        p["lat"] += random.uniform(-0.001, 0.001)
        p["lon"] += random.uniform(-0.001, 0.001)
        p["altitude"] += random.randint(-50, 50)
        p["speed"] += random.randint(-5, 5)
        p["track"] = (p["track"] + random.randint(-2, 2)) % 360
        p["rssi"] += random.uniform(-0.5, 0.5)
        p["last_seen"] = now

    # ---- poista vanhat ----
    before = len(planes)
    planes = [p for p in planes if now - p["last_seen"] < PLANE_TTL]
    removed = before - len(planes)

    if removed:
        print(f"{datetime.now()} Poistettu {removed} vanhaa konetta")

    # ---- kirjoita JSON atomisesti ----
    data = {
        "now": now,
        "messages": len(planes),
        "aircraft": planes
    }

    with open(TMP_FILE, "w") as f:
        json.dump(data, f, indent=2)

    os.replace(TMP_FILE, JSON_FILE)

    time.sleep(1)