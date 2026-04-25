#!/usr/bin/env python3

# by mika.nokka1@gmail.com 2026

import subprocess, select
from datetime import datetime, timedelta
import json, os, time
import csv
import folium
import signal
import sys
import tty
import termios
import threading
from http.server import ThreadingHTTPServer, SimpleHTTPRequestHandler
from folium.plugins import PolyLineTextPath

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
DUMP_LOG="dump109.log"


planes_dict = {}
aircraft_db = {}
start_time = time.time()
last_planes = []
last_reset_time = "-"
last_dump_start_time = 0  
first_run_reset_shown = False  # ensimmäisen käynnistyksen reset-viesti
last_watchdog_reset = 0       

ICALEN=6
REGLEN=6   
TYPELEN=4
OPERATORLEN=8
FLIGHTLEN=6
WIDTH=200

HTTP_PORT = 8777    # open in browser: http://localhost:8777/map.html
#m = folium.Map(location=[61.0, 25.0], zoom_start=6)
m = folium.Map(
    location=[61.0, 25.0],
    zoom_start=6,
    tiles="OpenStreetMap",
    control_scale=True
)

#OFFILINE USAGE
#m = folium.Map(
#    location=[61.0, 25.0],
#    zoom_start=6,
#    tiles=None
#)

plane_colors = {}
COLOR_POOL = [
    "red","blue","green","purple","orange",
    "darkred","lightred","beige","darkblue",
    "darkgreen","cadetblue","darkpurple","white"
]

map_file = "map.html"
if os.path.exists(map_file):
    os.remove(map_file)

MAP_SAVE_INTERVAL = 200      
last_map_save = 0


dumplog = open(DUMP_LOG, "a")
dumplog.write(f"*************** NEW LOG ENTRY ****************************************\n")
dumplog.write(f"{datetime.now()}\n")

f=open(DEBUG_FILE, "a")  
f.write(f"*************** NEW LOG ENTRY ******************************************\n")
f.write(f"{datetime.now()}\n")


dfilename = f"Dashboard_{datetime.now().replace(microsecond=0)}"
dfilename = dfilename.replace(":", "-").replace(" ", "_") + ".txt"
dasboardf=open(dfilename, "w")
last_save_time = "-"
last_map_save_time = "-"



# ---------------- DEBUG ----------------
def debug(msg):
        f.write(f"{datetime.now()} {msg}\n")
        f.flush()

# ---------------- UNDER UPDATING JSON FILE SAFE READ----------------
def safe_read_json(path, last_good, retries=5, delay=0.05):
    for _ in range(retries):
        try:
            if not os.path.exists(path):
                return last_good
            with open(path, "r") as f:
                data = json.load(f)
            if "aircraft" in data:
                return data["aircraft"]
        except Exception as e:
            #pass
            debug(f"JSON read error: {e}")
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
        #if len(p["history"]) > 1:
        #    folium.PolyLine(
        #        locations=[p["history"][-2], (lat, lon)],
        #        color=color,
        #        weight=2,
        #        opacity=0.6
        #    ).add_to(m)

        # Historia-viiva + suuntanuoli
        if len(p["history"]) > 1:

            prev_point = p["history"][-2]
            current_point = (lat, lon)

            line = folium.PolyLine(
                locations=[prev_point, current_point],
                color=color,
                weight=2,
                opacity=0.8
            )

            line.add_to(m)

            PolyLineTextPath(
                line,
                "➜",
                repeat=False,
                offset=7,
                attributes={
                    "font-size": "16",
                    "fill": color
                }
            ).add_to(m)

        alt = p["state"][0]
        alt_text = "GROUND" if alt == "ground" else f"{int(alt)} ft"
        tooltip_text = (
            f"Flight: {p['flight']}\n"
            f"Reg: {p.get('registration','??')}\n"
            f"Operator: {p.get('operator','??')}\n"
            f"Type: {p.get('type','??')}\n"
            f"Altitude: {alt_text}\n"
            #f"Altitude: {p['state'][0]} ft\n"
            f"Speed: {p['state'][1]} kt\n"
            f"Track: {p['state'][2]}°\n"
            f"RSSI: {p['state'][5]}\n"
            f"Owner: {p.get('owner','??')}\n"
            f"Manufacturer: {p.get('manufacturername','??')}"
        )

        folium.CircleMarker(
            location=[lat, lon],
            radius=2,
            color=color,
            fill=True,
            fill_color=color,
            fill_opacity=0.8,
            tooltip=tooltip_text
        ).add_to(m)

    global last_map_save
    now_time = time.time()
    if now_time - last_map_save > MAP_SAVE_INTERVAL:
        tmp = map_file + ".tmp"
        m.save(tmp)
        os.replace(tmp, map_file)
      
        last_map_save = now_time

# ---------------- UTILITIES ----------------

def parse_alt(val):
    if val == "ground":
        return "ground"

    if isinstance(val, str):
        val = val.replace(".", "").replace(",", ".")

    try:
        return round(float(val), 0)
    except (TypeError, ValueError):
        return 0

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
                "owner": row.get("owner","??"),
                "model": row.get("model","??")
            }

def start_http_server():
    class QuietHandler(SimpleHTTPRequestHandler):
        def log_message(self, format, *args):
            pass

    server = ThreadingHTTPServer(("0.0.0.0", HTTP_PORT), QuietHandler)

    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()

    print(f"HTTP server running:")
    print(f"http://localhost:{HTTP_PORT}/{map_file}")

    debug(f"HTTP server started on port {HTTP_PORT}")

    return server            

# ---------------- HELPER ----------------
# ---------------- HELPERS ----------------
def safe_float(val, default=0.0):
    if val == "ground":
        return "ground"
    if isinstance(val, str):
        val = val.replace(".", "").replace(",", ".")
    try:
        return float(val)
    except (TypeError, ValueError):
        return default



def extract_state(p):
    alt_raw = p.get("altitude")
    on_ground = p.get("on_ground")

    if alt_raw == "ground" or on_ground is True:
        alt = "ground"
    else:
        alt = safe_float(alt_raw)
        alt = round(alt, 0)

    return (
        alt,
        round(safe_float(p.get("speed")), 0),
        round(safe_float(p.get("track")), 0),
        round(safe_float(p.get("lat")), 5),
        round(safe_float(p.get("lon")), 5),
        round(safe_float(p.get("rssi")), 1)
    )

# ---------------- DUMP MANAGEMENT ----------------
dump_proc = None
def start_dump(show_output=False, is_watchdog=False):
    global dump_proc, last_dump_start_time, last_reset_time
    global first_run_reset_shown, last_watchdog_reset
    global planes_dict, last_planes  # <--- lisätty nollaus

    now = time.time()

    if dump_proc and dump_proc.poll() is None:
        try:
            os.killpg(os.getpgid(dump_proc.pid), signal.SIGTERM)
            dump_proc.wait(timeout=7)
        except Exception as e:
            debug(f"Failed to stop dump1090: {e} \n")
    else:
        debug("dump1090 already dead, no need to kill\n")

        time.sleep(10) # pieni viive varmistamaan prosessin kuoleminen

    
    dump_proc = subprocess.Popen(
        ["dump1090-mutability", "--net", "--write-json", JSON_DIR],
        #stdout=subprocess.PIPE, # if pipe not flushed, crashing
        #stderr=subprocess.STDOUT,
        stdout=dumplog,
        stderr=dumplog,
        text=True,
        preexec_fn=os.setsid
    )

    
    if dump_proc.poll() is not None:
        debug("dump1090 died immediately!\n")

        if dump_proc.stdout:
            try:
                debug("---- dump1090 output ----\n")
                debug(dump_proc.stdout.read())
                debug("\ņ------------------------\n")
            except Exception as e:
                debug(f"Failed to read output: {e}")
    
    #subprocess.run(["rtl_test", "-t"], timeout=5)

    last_dump_start_time = now


    if not first_run_reset_shown:
        last_reset_time = datetime.now().strftime("%H:%M:%S")
        first_run_reset_shown = True
        print("Dump1090 started/restarted (initial run)")
        debug("Dump1090 started/restarted (initial run)\n")
    elif is_watchdog and now - last_watchdog_reset > WATCHDOG_MIN_INTERVAL:
        last_watchdog_reset = now
        last_reset_time = datetime.now().strftime("%H:%M:%S")
        print(f"⚠ Watchdog reset at {last_reset_time}")
        debug(f"Watchdog reset at {last_reset_time}\n")

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

# ----------------------- STORE DASHBOARD ---------------------------------------------------------

def write_snapshot(planes_dict):
    
    global last_save_time

    last_save_time = datetime.now().strftime("%H:%M:%S")

    dasboardf.write("="*WIDTH + "\n")
    dasboardf.write(f"DASHBOARD {datetime.now()}    Map:{map_file}   Debug:{DEBUG_FILE}   Dump:{DUMP_LOG}   Dashboard file:{dfilename}")
    dasboardf.write(f"Running: {format_runtime(time.time() - start_time)}\n")
    dasboardf.write(f"Last reset: {last_reset_time}\n")
    dasboardf.write("="*WIDTH + "\n")

    dasboardf.write(
        f"{'ICAO':<6} {'Reg':<6} {'Type':<4} {'Op':<8} {'Flight':<6} "
        f"{'Lat':>9} {'Lon':>9} {'Alt':>6} {'Spd':>6} {'Trk':>6} "
        f"{'RSSI':>6} {'Msgs':>5} {'FirstSeen':>8} {'Vert':>6} {'Squawk':>6} "
        f"{'Alert':>5} {'OnG':>3} {'Status':>7} {'Removed':>8} "
        f"{'Callsign'} {'Owner'} {'Manufact'} {'Model'}\n"
    )

    dasboardf.write("-"*WIDTH + "\n")

    if not planes_dict:
        dasboardf.write("Ei havaintoja – ohjelma toimii\n")
    else:
        for icao, p in planes_dict.items():
            s = p["state"]
            
            alt_display = "GND" if s[0] == "ground" else f"{int(s[0])}"
            dasboardf.write(
                f"{icao:06X} "
                f"{p['registration'][:6]:<6} "
                f"{p['type'][:4]:<4} "
                f"{p['operator'][:8]:<8} "
                f"{p['flight'][:6]:<6} "
                f"{s[3]:>9.5f} {s[4]:>9.5f} "
                f"{alt_display:>6} {s[1]:>6} {s[2]:>6} "
                #f"{s[0]:>6} {s[1]:>6} {s[2]:>6} "
                f"{s[5]:>6} "
                f"{p['messages']:>5} "
                f"{p['first_seen']:>8} "
                f"{p['vertical']:>6} "
                f"{p['squawk']:>6} "
                f"{str(p['alert']):>5} "
                f"{str(p['on_ground']):>3} "
                f"{p['status']:>7} "
                f"{(p['removed_time'] or '-'):>8} "
                f"{p['operatorcallsign']} | "
                f"{p['owner']} | "
                f"{p['manufacturername']} | "
                f"{p['model']}\n"
            )

    dasboardf.write("="*WIDTH + "\n\n")
    dasboardf.flush()


def save_map_snapshot():
    global last_map_save_time

    filename = f"map_{datetime.now().replace(microsecond=0)}"
    filename = filename.replace(":", "-").replace(" ", "_") + ".html"

    tmp = filename + ".tmp"
    m.save(tmp)
    os.replace(tmp, filename)

    last_map_save_time = datetime.now().strftime("%H:%M:%S")

    print(f"Map saved: {filename}")




# ---------------- START ----------------
print("Starting...")
http_server = start_http_server()
load_aircraft_database()
start_dump(show_output=True)
time.sleep(3)

# ---------------- DASHBOARD ----------------
def print_dashboard_header():
    clear_screen()
    print("="*WIDTH)
    print(f"DASHBOARD {datetime.now()}    Map:{map_file}   Debug:{DEBUG_FILE}   Dump:{DUMP_LOG}   Dashboard file:{dfilename}")
    print(f"Running: {format_runtime(time.time() - start_time)}")
    #print(f"Last reset: {last_reset_time}   Last saved (s): {last_save_time}   (m save mapfile)")
    print(f"Last reset: {last_reset_time}   Last saved (s): {last_save_time}   Map saved: {last_map_save_time}")
    print("="*WIDTH)
    print(
        f"{'ICAO':<6} {'Reg':<6} {'Type':<4} {'Op':<8} {'Flight':<6} "
        f"{'Lat':>9} {'Lon':>9} {'Alt':>6} {'Spd':>6} {'Trk':>6} "
        f"{'RSSI':>6} {'Msgs':>5} {'FirstSeen':>8} {'Vert':>6} {'Squawk':>6} "
        f"{'Alert':>5} {'OnG':>3} {'Status':>7} {'Removed':>8} "
        f"{'Callsign'} {'Owner'} {'Manufact'} {'Model'}" 
    )
    print("-"*WIDTH)

# ---------------- LOOP ----------------
last_heartbeat = time.time()

try:

    fd = sys.stdin.fileno()
    old = termios.tcgetattr(fd)
    tty.setcbreak(fd)

    debugcount=0
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

        debugcount=debugcount+1
        if (debugcount > 60):
            debugcount=0
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
                    "manufacturername": meta.get("manufacturername","??"),
                    "model": meta.get("model","??")
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
                alt_display = "GND" if s[0] == "ground" else f"{int(s[0])}"
                print(
                    f"{icao:06X} "
                    f"{p['registration'][:6]:<6} "
                    f"{p['type'][:4]:<4} "
                    f"{p['operator'][:8]:<8} "
                    f"{p['flight'][:6]:<6} "
                    f"{s[3]:>9.5f} {s[4]:>9.5f} "
                    f"{alt_display:>6} {s[1]:>6} {s[2]:>6} "
                    #f"{s[0]:>6} {s[1]:>6} {s[2]:>6} "
                    f"{s[5]:>6} "
                    f"{p['messages']:>5} "
                    f"{p['first_seen']:>8} "
                    f"{p['vertical']:>6} "
                    f"{p['squawk']:>6} "
                    f"{str(p['alert']):>5} "
                    f"{str(p['on_ground']):>3} "
                    f"{p['status']:>7} "
                    f"{(p['removed_time'] or '-'):>8} "
                    f"{p['operatorcallsign']} | "
                    f"{p['owner']} | "
                    f"{p['manufacturername']} | "
                    f"{p['model']} "
                )

        print("="*WIDTH)
        update_all_planes_map(planes_dict)
       
        if select.select([sys.stdin], [], [], 0)[0]:
            key = sys.stdin.read(1)
            if key == "s":
                print("S painettu")
                time.sleep(0.2)
                write_snapshot(planes_dict)

            elif key == "m":
                print("M painettu")
                time.sleep(0.2)
                save_map_snapshot()    
        time.sleep(0.5)

except KeyboardInterrupt:
    if dump_proc:
        os.killpg(os.getpgid(dump_proc.pid), signal.SIGTERM)
    print("CTRL-C Stopped")
    debug("CTRL-C Stopped\n")
    dumplog.write(f"CTRL-C Stopped\n")

finally:
    termios.tcsetattr(fd, termios.TCSADRAIN, old)
    dumplog.close()
    f.close()
    dasboardf.close()