#!/usr/bin/env python3
import time
import random

import os

def beep():
    os.system("paplay /usr/share/sounds/freedesktop/stereo/complete.oga &")

def flash_screen():
    print("\033[?5h", end="", flush=True)  # invert screen
    time.sleep(0.1)
    print("\033[?5l", end="", flush=True)  # takaisin normaaliksi

print("Testi käynnissä – uusi 'kone' ilmestyy satunnaisesti.")
print("Paina Ctrl+C lopettaaksesi.\n")

plane_id = 1

try:
    while True:

        time.sleep(2)

        if random.random() < 0.5:  # 50% todennäköisyys
            print(f"\nNEW AIRCRAFT DETECTED: TEST{plane_id:03d}")

            beep()
            flash_screen()

            plane_id += 1

        else:
            print("Ei uusia koneita...")

except KeyboardInterrupt:
    print("\nLopetetaan testi.")