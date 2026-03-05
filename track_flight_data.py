#!/usr/bin/env python3
import subprocess, select
from datetime import datetime, timedelta
import json, os, time
import csv

# --------------------- ASETUKSET ---------------------
JSON_DIR = "./json_data"
JSON_FILE = os.path.join(JSON_DIR, "aircraft.json")
EXCEL_FILE = "./aircraftDatabase.csv"
REMOVE_TIMEOUT = 180
HEARTBEAT_INTERVAL = 5

planes_dict = {}
aircraft_db = {}
start_time = time.time()

# ---------------- LUE CSV ----------------
def load_aircraft_database():
    global aircraft_db
    if not os.path.exists(EXCEL_FILE):
        print("CSV metadata file not found.")
        return

    with open(EXCEL_FILE, newline='', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            raw_icao = row.get("icao24")
            if not raw_icao:
                continue
            try:
                icao_decimal = int(str(raw_icao).strip().lower().replace("0x",""), 16)
            except ValueError:
                continue
            aircraft_db[icao_decimal] = {
                "registration": (row.get("registration") or "??").strip(),
                "typecode": (row.get("typecode") or "??").strip(),
                "operator": (row.get("operator") or "??").strip(),
            }

# ---------------- HELPER ----------------
def extract_state(p):
    return (
        round(p.get("altitude", 0), 0),
        round(p.get("speed", 0), 0),
        round(p.get("track", 0), 0),
        round(p.get("lat", 0.0), 5),
        round(p.get("lon", 0.0), 5),
        round(p.get("rssi", 0.0), 1)
    )

def state_changed(old, new):
    return old != new

def clear_screen():
    os.system("cls" if os.name == "nt" else "clear")

def format_runtime(seconds):
    td = timedelta(seconds=int(seconds))
    return str(td)

# ---------------- START ----------------
load_aircraft_database()

print("Käynnistetään dump1090...")
proc = subprocess.Popen(
    ["dump1090-mutability", "--net", "--write-json", JSON_DIR],
    stdout=subprocess.PIPE,
    stderr=subprocess.STDOUT,
    text=True
)

print("\nLuen tikun alkuraportteja 6 sekuntia...")
initial_start = time.time()
while time.time() - initial_start < 6:
    if proc.stdout in select.select([proc.stdout], [], [], 0.1)[0]:
        line = proc.stdout.readline()
        if line:
            print(line.strip())

def print_dashboard_header():
    clear_screen()
    print("="*210)
    print(f"FLIGHT TRANSPONDER – RIKASTETTU NÄKYMÄ    {datetime.now()}")
    print(f"Running time: {format_runtime(time.time() - start_time)}")
    print("="*210)

    print(f"{'ICAO':<8} {'Reg':<10} {'Type':<6} {'Operator':<20} {'Flight':<8} "
          f"{'Lat':>8} {'Lon':>8} {'Alt':>6} {'Spd':>5} {'Track':>6} {'RSSI':>6} "
          f"{'Msgs':>6} {'Msg/s':>6} {'First':>8} "  # ADDED
          f"{'Vertical':>8} {'Squawk':>6} {'Alert':>5} {'OnGrd':>5} "
          f"{'Status':>9} {'Removed':>9}")

    print("-"*210)

print_dashboard_header()
print("Odottamassa koneita JSONista...")
print("="*210)
time.sleep(1)

# ---------------- PÄÄSILMUKKA ----------------
last_heartbeat = time.time()

try:
    while True:
        now = time.time()

        planes = []
        if os.path.exists(JSON_FILE):
            try:
                with open(JSON_FILE,"r") as f:
                    data = json.load(f)
                planes = data.get("aircraft", [])
            except json.JSONDecodeError:
                planes = []

        # ---- Päivitä koneet ----
        for p in planes:
            raw_icao = p.get("hex")
            if not raw_icao:
                continue

            try:
                icao_decimal = int(str(raw_icao), 16)
            except (ValueError, TypeError):
                continue

            meta = aircraft_db.get(
                icao_decimal,
                {"registration":"??","typecode":"??","operator":"??"}
            )

            flight = p.get("flight", "?")
            state = extract_state(p)

            messages = p.get("messages", 0)  # ADDED

            if icao_decimal not in planes_dict:

                planes_dict[icao_decimal] = {
                    "flight": flight,
                    "state": state,
                    "first_seen": datetime.now().strftime("%H:%M:%S"),
                    "last_seen": now,
                    "status": "ACTIVE",
                    "removed_time": None,
                    "registration": meta["registration"],
                    "type": meta["typecode"],
                    "operator": meta["operator"],
                    "vertical": p.get("vertical_rate","??"),
                    "squawk": p.get("squawk","??"),
                    "alert": p.get("alert","??"),
                    "on_ground": p.get("on_ground","??"),
                    "messages": messages,
                    "prev_messages": messages,     # ADDED
                    "msg_rate": 0                  # ADDED
                }

            else:

                pdata = planes_dict[icao_decimal]

                # ---- Msg/s laskenta ----  ADDED
                msg_delta = messages - pdata["prev_messages"]
                if msg_delta < 0:
                    msg_delta = 0
                pdata["msg_rate"] = msg_delta
                pdata["prev_messages"] = messages

                # ---- state update FIX ----
                if state_changed(pdata["state"], state):
                    pdata["state"] = state
                    pdata["last_seen"] = now

                pdata["flight"] = flight
                pdata["vertical"] = p.get("vertical_rate","??")
                pdata["squawk"] = p.get("squawk","??")
                pdata["alert"] = p.get("alert","??")
                pdata["on_ground"] = p.get("on_ground","??")
                pdata["messages"] = messages

                if pdata["status"] == "REMOVED":
                    pdata["status"] = "ACTIVE"
                    pdata["removed_time"] = None

        # ---- Hiljaisuustarkistus ----
        for icao, pdata in planes_dict.items():
            if pdata["status"] == "ACTIVE":
                if now - pdata["last_seen"] > REMOVE_TIMEOUT:
                    pdata["status"] = "REMOVED"
                    pdata["removed_time"] = datetime.now().strftime("%H:%M:%S")

        # ---- Tulostus ----
        print_dashboard_header()

        if not planes_dict:
            if now - last_heartbeat >= HEARTBEAT_INTERVAL:
                print("Ei havaintoja JSONista – ohjelma toimii.")
                last_heartbeat = now
        else:
            for icao, pdata in planes_dict.items():
                s = pdata["state"]
                removed_time = pdata["removed_time"] or "-"

                print(f"{icao:06X} {pdata['registration']:<10} {pdata['type']:<6} "
                      f"{pdata['operator']:<20} {pdata['flight']:<8} "
                      f"{s[3]:>8} {s[4]:>8} {s[0]:>6} {s[1]:>5} {s[2]:>6} {s[5]:>6} "
                      f"{pdata['messages']:>6} "
                      f"{pdata['msg_rate']:>6} "  # ADDED
                      f"{pdata['first_seen']:>8} "  # ADDED
                      f"{pdata['vertical']:>8} {pdata['squawk']:>6} "
                      f"{str(pdata['alert']):>5} {str(pdata['on_ground']):>5} "
                      f"{pdata['status']:>9} {removed_time:>9}")

            print("="*210)
            print(f"Yhteensä päivän aikana nähtyjä koneita: {len(planes_dict)}")

        time.sleep(1)

except KeyboardInterrupt:
    clear_screen()
    print("\nLopetetaan ohjelma...")
    proc.terminate()