#!/usr/bin/env python3
from datetime import datetime
import json, os, time

JSON_FILE = "./json_data/aircraft_backup.json"
REMOVE_TIMEOUT = 180  # sekuntia, 3 minuuttia
HEARTBEAT_INTERVAL = 5

planes_dict = {}  # icao -> {flight, state, last_seen, status, removed_time}
last_heartbeat = time.time()

def get_state(p):
    """Yksi tuple kaikista muuttuvista arvoista"""
    return (
        round(p.get("altitude",0),0),
        round(p.get("speed",0),0),
        round(p.get("track",0),0),
        round(p.get("lat",5),5),
        round(p.get("lon",5),5),
        round(p.get("rssi",0.0),1)
    )

try:
    while True:
        now = time.time()

        # Lue JSON
        if os.path.exists(JSON_FILE):
            try:
                with open(JSON_FILE,"r") as f:
                    data = json.load(f)
                planes = data.get("aircraft",[])
            except json.JSONDecodeError:
                planes = []
                time.sleep(0.1)
                continue
        else:
            planes = []

        # Päivitä aktiiviset koneet
        for p in planes:
            icao = p.get("hex","?")
            flight = p.get("flight","?")
            state = get_state(p)
            planes_dict[icao] = {
                "flight": flight,
                "state": state,
                "last_seen": now,
                "status": "ACTIVE",
                "removed_time": None
            }

        # Tarkista timeout / poistuneet
        for icao, p in planes_dict.items():
            if p["status"] == "ACTIVE" and now - p["last_seen"] > REMOVE_TIMEOUT:
                p["status"] = "REMOVED"
                p["removed_time"] = datetime.now().strftime("%H:%M:%S")

        # Heartbeat
        if not planes_dict and now - last_heartbeat >= HEARTBEAT_INTERVAL:
            print(f"{datetime.now()} Ohjelma toimii, ei havaintoja")
            last_heartbeat = now

        # Tulosta snapshot-taulukko
        if planes_dict:
            print("\n" + "="*100)
            print(f"{datetime.now()} KOKO PÄIVÄN SNAPSHOT")
            print("-"*100)
            print(f"{'ICAO':<8} {'Flight':<6} {'Alt':>6} {'Spd':>4} {'Hdg':>3} "
                  f"{'Lat':>8} {'Lon':>8} {'RSSI':>6} {'Status':>8} {'Removed At':>10}")
            for icao, p in planes_dict.items():
                s = p["state"]
                removed_time = p["removed_time"] if p["removed_time"] else "-"
                print(f"{icao:<8} {p['flight']:<6} {s[0]:>6} {s[1]:>4} {s[2]:>3} "
                      f"{s[3]:>8} {s[4]:>8} {s[5]:>6} {p['status']:>8} {removed_time:>10}")
            print("="*100 + "\n")

        time.sleep(1)

except KeyboardInterrupt:
    print("\nLopetetaan ohjelma...")