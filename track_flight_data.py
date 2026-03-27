#!/usr/bin/env python3

# by mika.nokka1@gmail.com 2026

import subprocess, select
from datetime import datetime, timedelta
import json, os, time
import csv
import folium
import signal

# --------------------- ASETUKSET ---------------------
JSON_DIR = "./json_data"
JSON_FILE = os.path.join(JSON_DIR, "aircraft.json")
EXCEL_FILE = "./aircraftDatabase.csv"

REMOVE_TIMEOUT = 180
LOST_TIMEOUT = 10
HEARTBEAT_INTERVAL = 5
JSON_STALE_TIMEOUT = 300  # 5 minuuttia

DUMP_START_GRACE = 10  # dumpille aikaa käynnistyä resetin jälkeen
WATCHDOG_MIN_INTERVAL = 30  # sekunteina, vähintään 30s väli watchdog reset logille

DEBUG_FILE = "debug.log"
DUMP_LOG="dump109.l0g"

planes_dict = {}
aircraft_db = {}
start_time = time.time()
last_planes = []
last_reset_time = "-"
last_dump_start_time = 0  
first_run_reset_shown = False  # ensimmäisen käynnistyksen reset-viesti
last_watchdog_reset = 0       # viimeisin watchdog-resetin aikaleima

ICALEN=6
REGLEN=6   
TYPELEN=4
OPERATORLEN=8
FLIGHTLEN=6
WIDTH=200

    
m = folium.Map(location=[61.0, 25.0], zoom_start=6)

plane_colors = {}
COLOR_POOL = [
    "red","blue","green","purple","orange",
    "darkred","lightred","beige","darkblue",
    "darkgreen","cadetblue","darkpurple","white"
]

map_file = "map.html"
if os.path.exists(map_file):
    os.remove(map_file)

dumplog = open(DUMP_LOG, "a")

# ---------------- DEBUG ----------------
def debug(msg):
    with open(DEBUG_FILE, "a") as f:
        f.write(f"{datetime.now()} {msg}\n")

# ---------------- JSON SAFE ----------------
def safe_read_json(path, last_good, retries=5, delay=0.05):
    for _ in range(retries):
        try:
            if not os.path.exists(path):
                return last_good
            with open(path, "r") as f:
                data = json.load(f)
            if "aircraft" in data:
                return data["aircraft"]
        except Exception:
            pass
        time.sleep(delay)
    return last_good

# ---------------- MAP ----------------
def get_plane_color(icao):
    if icao not in plane_colors:
        plane_colors[icao] = COLOR_POOL[len(plane_colors) % len(COLOR_POOL)]
    return plane_colors[icao]

def update_all_planes_map(planes_dict):

    global m

    for icao, p in planes_dict.items():
        lat = p["state"][3]
        lon = p["state"][4]
        if lat == 0 or lon == 0:
            continue
        if "history" not in p:
            p["history"] = []
        if p["history"] and p["history"][-1] == (lat, lon):
            continue
        p["history"].append((lat, lon))
        color = get_plane_color(icao)
        
        # Historia-viiva
        if len(p["history"]) > 1:
            folium.PolyLine(
                locations=[p["history"][-2], (lat, lon)],
                color=color,
                weight=2,
                opacity=0.6
            ).add_to(m)

        tooltip_text = (
            f"Flight: {p['flight']}\n"
            f"Reg: {p.get('registration','??')}\n"
            f"Operator: {p.get('operator','??')}\n"
            f"Type: {p.get('type','??')}\n"
            f"Altitude: {p['state'][0]} ft\n"
            f"Speed: {p['state'][1]} kt\n"
            f"Track: {p['state'][2]}°\n"
            f"RSSI: {p['state'][5]}\n"
            f"Owner: {p.get('owner','??')}\n"
            f"Manufacturer: {p.get('manufacturername','??')}"
        )

        folium.CircleMarker(
            location=[lat, lon],
            radius=5,
            color=color,
            fill=True,
            fill_color=color,
            fill_opacity=0.8,
            tooltip=tooltip_text
        ).add_to(m)

    tmp = map_file + ".tmp"
    m.save(tmp)
    os.replace(tmp, map_file)

# ---------------- UTIL ----------------
def beep():
    os.system("paplay /usr/share/sounds/freedesktop/stereo/complete.oga &")

def flash_screen():
    print("\033[?5h", end="", flush=True)
    time.sleep(0.1)
    print("\033[?5l", end="", flush=True)

def clear_screen():
    os.system("cls" if os.name == "nt" else "clear")

def format_runtime(seconds):
    return str(timedelta(seconds=int(seconds)))

# ---------------- CSV ----------------
def load_aircraft_database():
    if not os.path.exists(EXCEL_FILE):
        return
    with open(EXCEL_FILE, newline='', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            raw_icao = row.get("icao24")
            if not raw_icao:
                continue
            try:
                icao_decimal = int(str(raw_icao).strip().lower().replace("0x",""), 16)
            except:
                continue
            aircraft_db[icao_decimal] = {
                "registration": row.get("registration","??"),
                "typecode": row.get("typecode","??"),
                "operator": row.get("operator","??"),
                "manufacturername": row.get("manufacturername","??"),
                "operatorcallsign": row.get("operatorcallsign","??"),
                "owner": row.get("owner","??")
            }

# ---------------- HELPER ----------------
def extract_state(p):
    return (
        round(p.get("altitude") or 0,0),
        round(p.get("speed") or 0,0),
        round(p.get("track") or 0,0),
        round(p.get("lat") or 0.0,5),
        round(p.get("lon") or 0.0,5),
        round(p.get("rssi") or 0.0,1)
    )

# ---------------- DUMP MANAGEMENT ----------------
dump_proc = None
def start_dump(show_output=False, is_watchdog=False):
    global dump_proc, last_dump_start_time, last_reset_time
    global first_run_reset_shown, last_watchdog_reset
    global planes_dict, last_planes  # <--- lisätty nollaus

    now = time.time()

    # 🔹 Tappaa kaikki vanhat dump1090-prosessit
    #try:
    #    subprocess.run(["pkill", "-f", "dump1090-mutability"], check=False)
    #except Exception as e:
    #    debug(f"pkill failed: {e}")

    #if dump_proc:
     #   debug(f"Old dump status: {dump_proc.poll()}")
     #   try:
     #       os.killpg(os.getpgid(dump_proc.pid), signal.SIGTERM)
     #       dump_proc.wait(timeout=5)   # 🔴 TÄRKEIN RIVI
     #   except Exception as e:
     #       debug(f"Failed to stop dump1090: {e}")


    if dump_proc and dump_proc.poll() is None:
        try:
            os.killpg(os.getpgid(dump_proc.pid), signal.SIGTERM)
            dump_proc.wait(timeout=7)
        except Exception as e:
            debug(f"Failed to stop dump1090: {e}")
    else:
        debug("dump1090 already dead, no need to kill")

        time.sleep(10) # pieni viive varmistamaan prosessin kuoleminen

    
    # 🔹 Käynnistä uusi dump1090
    dump_proc = subprocess.Popen(
        ["dump1090-mutability", "--net", "--write-json", JSON_DIR],
        #stdout=subprocess.PIPE,
        #stderr=subprocess.STDOUT,
        stdout=dumplog,
        stderr=dumplog,

        text=True,
        preexec_fn=os.setsid
    )
    #time.sleep(5)
    
    if dump_proc.poll() is not None:
        print("dump1090 died immediately!")

        if dump_proc.stdout:
            try:
                print("---- dump1090 output ----")
                print(dump_proc.stdout.read())
                print("------------------------")
            except Exception as e:
                print(f"Failed to read output: {e}")
    
    #subprocess.run(["rtl_test", "-t"], timeout=5)

    last_dump_start_time = now

    # 🔹 Reset-viesti
    if not first_run_reset_shown:
        last_reset_time = datetime.now().strftime("%H:%M:%S")
        first_run_reset_shown = True
        print("Dump1090 started/restarted (initial run)")
        debug("Dump1090 started/restarted (initial run)")
    elif is_watchdog and now - last_watchdog_reset > WATCHDOG_MIN_INTERVAL:
        last_watchdog_reset = now
        last_reset_time = datetime.now().strftime("%H:%M:%S")
        print(f"⚠ Watchdog reset at {last_reset_time}")
        debug(f"Watchdog reset at {last_reset_time}")
        # 🔹 Tyhjennetään vanhat lentokoneet resetin yhteydessä
        #planes_dict.clear()
        #last_planes = []
    else:
        debug("Dump1090 restarted without reset message (watchdog too recent)")

    if show_output and dump_proc.stdout:
        timeout = 5
        start = time.time()
        while time.time() - start < timeout:
            ready, _, _ = select.select([dump_proc.stdout], [], [], 0.1)
            for stream in ready:
                line = stream.readline()
                if line:
                    print(line, end="")
    else:
        time.sleep(5)

def check_json_fresh():
    if not os.path.exists(JSON_FILE):
        return False
    last_mod = os.path.getmtime(JSON_FILE)
    return time.time() - last_mod < JSON_STALE_TIMEOUT

# ---------------- START ----------------
load_aircraft_database()
start_dump(show_output=True)
time.sleep(3)

# ---------------- DASHBOARD ----------------
def print_dashboard_header():
    clear_screen()
    print("="*WIDTH)
    print(f"DASHBOARD {datetime.now()}")
    print(f"Running: {format_runtime(time.time() - start_time)}")
    print(f"Last reset: {last_reset_time}")
    print("="*WIDTH)
    print(
        f"{'ICAO':<6} {'Reg':<6} {'Type':<4} {'Op':<8} {'Flight':<6} "
        f"{'Lat':>9} {'Lon':>9} {'Alt':>6} {'Spd':>6} {'Trk':>6} "
        f"{'RSSI':>6} {'Msgs':>5} {'FirstSeen':>8} {'Vert':>6} {'Squawk':>6} "
        f"{'Alert':>5} {'OnG':>3} {'Status':>7} {'Removed':>8} "
        f"{'Callsign'} {'Owner'} {'Manufact'}"
    )
    print("-"*WIDTH)

# ---------------- LOOP ----------------
last_heartbeat = time.time()

try:
    while True:
        now = time.time()

        if now - last_dump_start_time < DUMP_START_GRACE:
            debug("Skip freshness check (grace)")
        else:
            if not check_json_fresh():
                start_dump(show_output=False, is_watchdog=True)

        if os.path.exists(JSON_FILE):
            planes = safe_read_json(JSON_FILE, last_planes)
            last_planes = planes
        else:
            planes = last_planes

        debug(f"planes={len(planes)} tracked={len(planes_dict)}")

        for p in planes:
            raw_icao = p.get("hex")
            if not raw_icao:
                continue
            try:
                icao = int(raw_icao,16)
            except:
                continue

            flight = (p.get("flight") or "?").strip()
            state = extract_state(p)
            messages = p.get("messages",0)
            vertical = p.get("vertical_rate","??")
            squawk = p.get("squawk","??")
            alert = p.get("alert","??")
            on_ground = p.get("on_ground","??")

            meta = aircraft_db.get(icao, {})

            if icao not in planes_dict:
                beep()
                flash_screen()
                planes_dict[icao] = {
                    "flight": flight,
                    "state": state,
                    "first_seen": datetime.now().strftime("%H:%M:%S"),
                    "last_seen": now,
                    "status": "ACTIVE",
                    "removed_time": None,
                    "registration": meta.get("registration","??"),
                    "type": meta.get("typecode","??"),
                    "operator": meta.get("operator","??"),
                    "vertical": vertical,
                    "squawk": squawk,
                    "alert": alert,
                    "on_ground": on_ground,
                    "messages": messages,
                    "operatorcallsign": meta.get("operatorcallsign","??"),
                    "owner": meta.get("owner","??"),
                    "manufacturername": meta.get("manufacturername","??")
                }
            else:
                pdata = planes_dict[icao]
                pdata["state"] = state
                pdata["last_seen"] = now
                pdata["flight"] = flight
                pdata["messages"] = messages
                pdata["vertical"] = vertical
                pdata["squawk"] = squawk
                pdata["alert"] = alert
                pdata["on_ground"] = on_ground

        for icao, pdata in planes_dict.items():
            age = now - pdata["last_seen"]
            if age > REMOVE_TIMEOUT:
                if pdata["status"] != "REMOVED":
                    pdata["status"] = "REMOVED"
                    pdata["removed_time"] = datetime.now().strftime("%H:%M:%S")
            elif age > LOST_TIMEOUT:
                pdata["status"] = "LOST"
            else:
                pdata["status"] = "ACTIVE"

        print_dashboard_header()

        if not planes_dict:
            if now - last_heartbeat >= HEARTBEAT_INTERVAL:
                print("Ei havaintoja – ohjelma toimii")
                last_heartbeat = now
        else:
            for icao, p in planes_dict.items():
                s = p["state"]
                print(
                    f"{icao:06X} "
                    f"{p['registration'][:6]:<6} "
                    f"{p['type'][:4]:<4} "
                    f"{p['operator'][:8]:<8} "
                    f"{p['flight'][:6]:<6} "
                    f"{s[3]:>9.5f} {s[4]:>9.5f} "
                    f"{s[0]:>6} {s[1]:>6} {s[2]:>6} "
                    f"{s[5]:>6} "
                    f"{p['messages']:>5} "
                    f"{p['first_seen']:>8} "
                    f"{p['vertical']:>6} "
                    f"{p['squawk']:>6} "
                    f"{str(p['alert']):>5} "
                    f"{str(p['on_ground']):>3} "
                    f"{p['status']:>7} "
                    f"{(p['removed_time'] or '-'):>8} "
                    f"{p['operatorcallsign']} "
                    f"{p['owner']} "
                    f"{p['manufacturername']}"
                )

        print("="*WIDTH)
        update_all_planes_map(planes_dict)
        time.sleep(2)

except KeyboardInterrupt:
    if dump_proc:
        os.killpg(os.getpgid(dump_proc.pid), signal.SIGTERM)
    print("\nStopped")