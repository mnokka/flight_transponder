#!/usr/bin/env python3
import subprocess, select
from datetime import datetime, timedelta
import json, os, time
import csv

# --------------------- ASETUKSET ---------------------
JSON_DIR = "./json_data"

JSON_FILE = os.path.join(JSON_DIR, "aircraft.json")
# keep this for test sw usage JSON_FILE= os.path.join(JSON_DIR, "aircraft_backup.json")
EXCEL_FILE = "./aircraftDatabase.csv"
REMOVE_TIMEOUT = 180
HEARTBEAT_INTERVAL = 5

planes_dict = {}
aircraft_db = {}
start_time = time.time()

# ⭐ KORJAUS: viimeisin validi JSON data
last_planes = []

ICALEN=6
REGLEN=6   
TYPELEN=4
OPERATORLEN=8
FLIGHTLEN=6
MESSAGESLEN=4
RSSILEN=5
WIDTH=180

#########################################################################


def beep():
    os.system("paplay /usr/share/sounds/freedesktop/stereo/complete.oga &")

def flash_screen():
    print("\033[?5h", end="", flush=True)  # invert screen
    time.sleep(0.1)
    print("\033[?5l", end="", flush=True)  # takaisin normaaliksi


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
                "manufacturername": (row.get("manufacturername") or "??").strip(),
                "operatorcallsign": (row.get("operatorcallsign") or "??").strip(),
                "owner": (row.get("owner") or "??").strip()
            }

# ---------------- HELPER ----------------
def extract_state(p):
    alt = p.get("altitude") or 0
    spd = p.get("speed") or 0
    trk = p.get("track") or 0
    lat = p.get("lat") or 0.0
    lon = p.get("lon") or 0.0
    rssi = p.get("rssi") or 0.0
    return (
        round(alt, 0),
        round(spd, 0),
        round(trk, 0),
        round(lat, 5),
        round(lon, 5),
        round(rssi, 1)
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

# ---------------- DASHBOARD ----------------
def print_dashboard_header():
    clear_screen()
    print("="*WIDTH)
    print(f"FLIGHT TRANSPONDER – RIKASTETTU NÄKYMÄ    {datetime.now()}")
    print(f"Running time: {format_runtime(time.time() - start_time)}")
    print("="*WIDTH)

    print(
        f"{'ICAO':<{ICALEN}} {'Reg':<{REGLEN}} {'Type':<{TYPELEN}} "
        f"{'Operator':<{OPERATORLEN}} {'Flight':<{FLIGHTLEN}} "
        f"{'Lat':>9} {'Lon':>9} {'Alt':>6} {'Speed':>6} {'Track':>6} "
        f"{'RSSI':>6} {'Msgs':>5} {'FirstSeen':>8} {'Vert':>6} "
        f"{'Squawk':>6} {'Alert':>5} {'OnG':>3} {'Status':>7} {'Removed':>8} "
        f"{'Callsign'} {'Owner'} {'Manufact'}"
        )
    
    print("-"*WIDTH)

print_dashboard_header()
print("Odottamassa koneita JSONista...")
print("="*WIDTH)
time.sleep(0.5)

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
                last_planes = planes   # ⭐ tallennetaan viimeisin hyvä data

            except json.JSONDecodeError:
                planes = last_planes   # ⭐ käytetään edellistä dataa

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
                {"registration":"??","typecode":"??","operator":"??",
                 "manufacturername":"??","operatorcallsign":"??","owner":"??"}
            )

            flight = (p.get("flight") or "?").strip()
            state = extract_state(p)
            messages = p.get("messages", 0)

            if icao_decimal not in planes_dict:

                beep()
                flash_screen()

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
                    "manufacturername": meta["manufacturername"],
                    "operatorcallsign": meta["operatorcallsign"],
                    "owner": meta["owner"],
                    "vertical": p.get("vertical_rate","??"),
                    "squawk": p.get("squawk","??"),
                    "alert": p.get("alert","??"),
                    "on_ground": p.get("on_ground","??"),
                    "messages": messages,
                    "prev_messages": messages
                }
            else:
                pdata = planes_dict[icao_decimal]
                pdata["prev_messages"] = messages
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
            if pdata["status"] == "ACTIVE" and now - pdata["last_seen"] > REMOVE_TIMEOUT:
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
                print(
                    f"{icao:{ICALEN}X} "
                    f"{pdata['registration']:<{REGLEN}} "
                    f"{pdata['type']:<{TYPELEN}} "
                    f"{pdata['operator'][:OPERATORLEN]:<{OPERATORLEN}} "
                    f"{pdata['flight'][:FLIGHTLEN]:<{FLIGHTLEN}} "
                    f"{s[3]:>9.5f} "
                    f"{s[4]:>9.5f} "
                    f"{s[0]:>6} "
                    f"{s[1]:>6} "
                    f"{s[2]:>6} "
                    f"{s[5]:>6} "
                    f"{pdata['messages']:>5} "
                    f"{pdata['first_seen']:>8} "
                    f"{pdata['vertical']:>6} "
                    f"{pdata['squawk']:>6} "
                    f"{str(pdata['alert']):>5} "
                    f"{str(pdata['on_ground']):>3} "
                    f"{pdata['status']:>7} "
                    f"{removed_time:>8} "
                    f"{pdata['operatorcallsign']} "
                    f"{pdata['owner']} "
                    f"{pdata['manufacturername']}"
                )
                print("="*WIDTH)
            print(f"Yhteensä päivän aikana nähtyjä koneita: {len(planes_dict)}")

        time.sleep(0.5)

except KeyboardInterrupt:
    clear_screen()
    print("\nLopetetaan ohjelma...")
    proc.terminate()