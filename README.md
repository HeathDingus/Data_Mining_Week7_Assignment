# Traffic Accident Hotspot and Alternative Route App

A data mining application that uses real Kentucky State Police collision records to find crash hotspots, score road segments by crash severity, and compare route options across the Big Sandy area of eastern Kentucky (Pike, Floyd, Johnson, Magoffin, and Martin counties).

For a randomly chosen trip, the app builds three routes and draws them on an interactive map:

- **Fastest route** (blue): the shortest path by distance.
- **Safest route** (green): the path that balances distance against the crash severity recorded on each road segment.
- **Detour** (orange, dashed): a reroute around a real crash location that sits on the fastest route, so the blocked road is avoided.

Red circles mark the highest-severity crash hotspots found by clustering.

![Route map](images/route_map.png)

## How it works

1. **Load and clean the data.** County files are combined, duplicate incidents are dropped by `IncidentID`, and rows with missing or zero coordinates are removed. Latitude and longitude are merged into a single point geometry column.
2. **Build the road network.** The drivable road network for the area is downloaded from OpenStreetMap with OSMnx, and only the largest connected piece is kept so every trip has a valid route.
3. **Snap crashes to roads.** Each crash is matched to its nearest road segment. Segments are treated as two-way, so crashes on either direction count toward the same road.
4. **Score the risk.** Each crash gets a severity score of `1 + 5 * killed + 2 * injured`. Scores are summed per road segment.
5. **Route.** Fastest routes minimize distance. Safest routes minimize `length + K * risk`, where `K` is the number of meters of detour the router will accept to avoid one unit of crash severity (set to 100 in the script). The script also prints a comparison of several `K` values so the tradeoff between distance and risk is visible.
6. **Pick a scenario.** Start and destination points are sampled from real crash locations, and the incident is a crash that lies on the fastest route. The seed is printed each run so a scenario can be reproduced.
7. **Find hotspots.** DBSCAN density clustering (500 m radius, minimum 15 crashes) groups crashes into hotspots, ranked by total severity.
8. **Map it.** Folium draws the routes, markers, and hotspots and saves `route_map.html`, which opens in the browser automatically.

## Data

Crash data comes from the Kentucky State Police public collision portal, **Kentucky Collision Analysis for the Public** (http://crashinformationky.org/). Data is not included in this repository.

To reproduce the data:

1. Export collision records for Pike, Floyd, Johnson, Magoffin, and Martin counties, from January 1, 2024 to the present. The portal limits export size, so each county was exported separately.
2. Name each file `<County>_Incident.txt` and place them in a `data/` folder:

```
data/
├── Pike_Incident.txt
├── Floyd_Incident.txt
├── Johnson_Incident.txt
├── Magoffin_Incident.txt
└── Martin_Incident.txt
```

The script finds any file in `data/` ending in `_Incident.txt`, so counties can be added or removed by adding or removing files.

## Setup

Python 3.10 or newer is recommended.

```
pip install -r requirements.txt
```

If `geopandas` fails to install with `pip` on Windows, a conda environment is the easier route.

## Map tiles (CARTO API key)

The map background uses CARTO basemap tiles, which now require a free API key. Request one at https://carto.com/basemaps/apikey (no CARTO account needed), then set it as an environment variable in the same terminal window before running the script.

Windows PowerShell:

```
$env:CARTO_API_KEY = "your-key-here"
```

Windows Command Prompt:

```
set CARTO_API_KEY=your-key-here
```

macOS or Linux:

```
export CARTO_API_KEY="your-key-here"
```

Without a key the app still runs, but the map tiles carry an "API KEY REQUIRED" watermark. Do not put the key in the code or commit it. The saved `route_map.html` contains the key inside the tile URL, so it is listed in `.gitignore` and should not be published.

## For instructors and reviewers

The CARTO API key used to develop this project is included in the submission notes, not in this repository. To run the app with it:

1. Copy the key from the submission notes.
2. Open a terminal in the project folder and set the key for that terminal session (use the command for your system from the section above), for example in PowerShell: `$env:CARTO_API_KEY = "paste-key-here"`.
3. In the same terminal, run `python traffic_accident_app.py`.

If you run the code in a Jupyter notebook instead, add this as the first cell and run it before the rest:

```python
import os
os.environ['CARTO_API_KEY'] = 'paste-key-here'
```

The key only needs to be set once per terminal window. If the map still shows an "API KEY REQUIRED" watermark, force-refresh the browser page. Screenshots of the output are included in the `images/` folder, so the result can also be reviewed without running anything.

## Run

From the project folder:

```
python traffic_accident_app.py
```

The first run is slow because the road network is downloaded. Each run picks a new random scenario, prints route statistics to the terminal, saves `route_map.html`, and opens it in your default browser.

## Tools

Python, pandas, GeoPandas, OSMnx, NetworkX, scikit-learn (DBSCAN), Folium.

## Limitations

- **Risk is total severity, not a rate.** Busy roads naturally collect more crashes, so the safest route partly avoids high-traffic roads. Traffic volume (AADT) data would be needed to normalize this.
- **Severity weights are a judgment call.** The `1 / 5 / 2` weights for crashes, fatalities, and injuries are not calibrated against an official standard.
- **Limited time window.** The data covers January 2024 to the present, and recent reports can be incomplete while agencies are still filing them.
- **Rural road network.** Some trips have few or no alternative roads, so the safest route or the detour may match the fastest route, or no detour may exist.
- **Straight-line route drawing.** Routes are drawn between intersections, so winding roads can look straighter on the map than they are.
- **Demo scenarios.** Start, destination, and incident are sampled from crash records for demonstration. They are not real trips or live incidents.

## Acknowledgments

- Crash data: Kentucky State Police.
- Road network data: &copy; OpenStreetMap contributors.
- Map tiles: &copy; CARTO.
