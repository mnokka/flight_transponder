import folium

# Kartta Hämeenlinnaan
m = folium.Map(location=[60.995, 24.464], zoom_start=7)

# Testilentokone
folium.Marker(
    [60.25, 24.95],
    popup="TEST AIRCRAFT",
    tooltip="FIN101"
).add_to(m)

# Tallenna kartta
m.save("map.html")

print("Kartta luotu: map.html")