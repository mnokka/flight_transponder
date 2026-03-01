# flight_transponder
Info detector of flight transponders data, used tool: dump1090-mutability (SDR used: RTL-SDR V4)   


Install (linux version) of needed analyze tool: ```sudo apt-get install dump1090-mutability```

Reuired Python lib:
pip install openpyl

```python3 track_flight_data.py | tee /dev/tty & ``