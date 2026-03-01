#!/usr/bin/env python3
from datetime import datetime
import json, os, time

JSON_FILE = "./json_data/aircraft_backup.json"
REMOVE_TIMEOUT = 180  # sekuntia, 3 minuuttia
HEARTBEAT_INTERVAL = 5

planes_dict = {}  # icao -> tietue
last_heartbeat = time.time()


def get_state(p):
    """Yksi tuple kaikista muuttuvista arvoista"""
    return (
        round(p.get("altitude", 0), 0),
        round(p.get("speed", 0), 0),
        round(p.get("track", 0), 0),
        round(p.get("lat", 5), 5),
        round(p.get("lon", 5), 5),
        round(p.get("rssi", 0.0), 1)
    )


def clear_screen():
    os.system("cls" if os.name == "nt" else "clear")


try:
    while True:
        now = time.time()

        # ---------------- JSON LUKU ----------------
        if os.path.exists(JSON_FILE):
            try:
                with open(JSON_FILE, "r") as f:
                    data = json.load(f)
                planes = data.get("aircraft", [])
            except json.JSONDecodeError:
                time.sleep(0.1)
                continue
        else:
            planes = []

        # ---------------- PÄIVITYSLOGIIKKA ----------------
        for p in planes:
            icao = p.get("hex", "?")
            flight = p.get("flight", "?")
            state = get_state(p)

            if icao not in planes_dict:
                # UUSI kone
                planes_dict[icao] = {
                    "flight": flight,
                    "state": state,
                    "first_seen": datetime.now().strftime("%H:%M:%S"),
                    "last_seen": now,
                    "status": "ACTIVE",
                    "removed_time": None
                }
            else:
                # Olemassa oleva kone – päivitetään vain kentät
                planes_dict[icao]["flight"] = flight
                planes_dict[icao]["state"] = state
                planes_dict[icao]["last_seen"] = now

                # Jos oli poistunut ja palaa
                if planes_dict[icao]["status"] == "REMOVED":
                    planes_dict[icao]["status"] = "ACTIVE"
                    planes_dict[icao]["removed_time"] = None

        # ---------------- POISTOLOGIIKKA ----------------
        for icao, pdata in planes_dict.items():
            if (
                pdata["status"] == "ACTIVE"
                and now - pdata["last_seen"] > REMOVE_TIMEOUT
            ):
                pdata["status"] = "REMOVED"
                pdata["removed_time"] = datetime.now().strftime("%H:%M:%S")

        # ---------------- DASHBOARD ----------------
        clear_screen()

        if not planes_dict:
            if now - last_heartbeat >= HEARTBEAT_INTERVAL:
                print(f"{datetime.now()} Ohjelma toimii, ei havaintoja")
                last_heartbeat = now
        else:
            print("=" * 120)
            print(f"FLIGHT TRANSPONDER – KOKO PÄIVÄN NÄKYMÄ    {datetime.now()}")
            print("=" * 120)
            print(
                f"{'ICAO':<8} {'Flight':<8} "
                f"{'Alt(ft)':>7} {'Spd(kn)':>7} {'Hdg':>5} "
                f"{'Lat':>9} {'Lon':>9} {'RSSI':>7} "
                f"{'Status':>9} {'First':>8} {'Removed':>10}"
            )
            print("-" * 120)

            for icao, pdata in planes_dict.items():
                s = pdata["state"]
                removed_time = pdata["removed_time"] if pdata["removed_time"] else "-"

                print(
                    f"{icao:<8} {pdata['flight']:<8} "
                    f"{s[0]:>7} {s[1]:>7} {s[2]:>5} "
                    f"{s[3]:>9} {s[4]:>9} {s[5]:>7} "
                    f"{pdata['status']:>9} "
                    f"{pdata['first_seen']:>8} {removed_time:>10}"
                )

            print("=" * 120)
            print(f"Yhteensä päivän aikana nähtyjä koneita: {len(planes_dict)}")

        time.sleep(1)

except KeyboardInterrupt:
    clear_screen()
    print("\nLopetetaan ohjelma...")