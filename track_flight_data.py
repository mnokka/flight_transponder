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


ICALEN=6
REGLEN=6   
TYPELEN=4
OPERATORLEN=8
FLIGHTLEN=6
MESSAGESLEN=4
RSSILEN=5
WIDTH=180

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

# ---------------- Dashboard sarakkeet lyhennetty ----------------
    print(f"{'ICAO':<{ICALEN}} {'Reg':<{REGLEN}} {'Type':<{TYPELEN}} {'Operator':<{OPERATORLEN}} {'Flight':<6} "
      f"{'Lat':>7} {'Lon':>7} {'Alt':>5} {'Speed':>5} {'TrackAngle':>6} {'RSSI':>{RSSILEN}} "
      f"{'Msgs':>{MESSAGESLEN}} {'FirstSeen':>8} {'VertSpeed':>8} {'Squawk':>6} {'Alert':>5} {'OnG':>3} "
      f"{'Status':>7} {'Removed':>8} {'Callsign':<10} {'Owner':<10} {'Manufact':<15} ")
    print("-"*WIDTH)

    # ---------------- Dashboard sarakkeet ----------------
    # ICAO       -> Koneen ICAO-tunnus 6
    # Reg        -> Rekisteritunnus 6
    # Type       -> Lentokoneen tyyppikoodi ?
    # Operator   -> Lentoyhtiö tai operaattori ?
    # Flight     -> Lentotunnus / flight code ?
    # Lat / Lon  -> Sijainti 4 4 
    # Alt        -> Korkeus jalassa 5
    # Speed      -> Nopeus ?
    # TrackAngle -> Kurssi / heading
    # RSSI       -> Signaalin voimakkuus 5
    # Msgs       -> Viestien määrä 3
    # First      -> Ensimmäinen havainto 8 
    # VertSpeed  -> Vertikaalinopeus (nousu/lasku)
    # Squawk     -> Squawk-koodi
    # Alert      -> Hälytys / Emergency
    # OnG        -> Maassa / on ground
    # Manufact   -> Valmistaja
    # Callsign   -> Operaattorin kutsumerkki
    # Owner      -> Omistaja 30
    # Status     -> Tilanne ACTIVE / REMOVED 7
    # Removed    -> Viimeinen poistettu-aika 8


print_dashboard_header()
print("Odottamassa koneita JSONista...")
print("="*WIDTH)
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
                {"registration":"??","typecode":"??","operator":"??",
                 "manufacturername":"??","operatorcallsign":"??","owner":"??"}
            )

            flight = p.get("flight", "?")
            state = extract_state(p)
            messages = p.get("messages", 0)

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
                print(f"{icao:{ICALEN}X} {pdata['registration']:<{REGLEN}} {pdata['type']:<{TYPELEN}} "
                f"{pdata['operator'][:OPERATORLEN]:<{OPERATORLEN}} {pdata['flight'][:6]:<{FLIGHTLEN}} "
                f"{s[3]:>7} {s[4]:>7} {s[0]:>5} {s[1]:>5} {s[2]:>6} {s[5]:>5} "
                f"{pdata['messages']:>{MESSAGESLEN}} "
                f"{pdata['first_seen']:>8} {pdata['vertical']:>8} {pdata['squawk']:>6} "
                f"{str(pdata['alert']):>5} {str(pdata['on_ground']):>3} "
                f"{pdata['status']:>7} {removed_time:>8} {pdata['operatorcallsign']:<10} {pdata['owner']:<10} {pdata['manufacturername']:<15}")
                print("="*WIDTH)
            print(f"Yhteensä päivän aikana nähtyjä koneita: {len(planes_dict)}")

        time.sleep(1)

except KeyboardInterrupt:
    clear_screen()
    print("\nLopetetaan ohjelma...")
    proc.terminate()