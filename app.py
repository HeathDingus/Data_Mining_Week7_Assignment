import random
import webbrowser
from pathlib import Path

import folium
import geopandas as gpd
import networkx as nx
import numpy as np
import osmnx as ox
import pandas as pd
from sklearn.cluster import DBSCAN

data_dir = Path('data')
files = sorted(data_dir.rglob('*_[Ii]ncident.txt'))
if not files:
    raise FileNotFoundError(f'No *_incident.txt files found under {data_dir.resolve()}')
print('loading:', [f.name for f in files])

dfs = [pd.read_csv(f) for f in files]
ky_bs_area_data = pd.concat(dfs, ignore_index=True)
ky_bs_area_data = ky_bs_area_data.drop_duplicates(subset='IncidentID')
ky_bs_area_data = ky_bs_area_data.drop(columns=['Unnamed: 38'], errors='ignore')
ky_bs_area_data = ky_bs_area_data.dropna(subset=['Latitude', 'Longitude'])
ky_bs_area_data = ky_bs_area_data[
    (ky_bs_area_data.Latitude != 0) & (ky_bs_area_data.Longitude != 0)
]

ky_bs_area_data = gpd.GeoDataFrame(
    ky_bs_area_data.drop(columns=['Latitude', 'Longitude']),
    geometry=gpd.points_from_xy(ky_bs_area_data.Longitude, ky_bs_area_data.Latitude),
    crs='EPSG:4326',
)
ky_bs_area_data = ky_bs_area_data.rename_geometry('Long_Lat')

df = ky_bs_area_data
df['long'] = df.Long_Lat.x
df['lat'] = df.Long_Lat.y

pad = 0.02

G = ox.graph_from_bbox(
    bbox=(df.long.min() - pad, df.lat.min() - pad, df.long.max() + pad, df.lat.max() + pad),
    network_type='drive',
)
G = ox.truncate.largest_component(G, strongly=True)

nearest = ox.distance.nearest_edges(G, X=df.long.values, Y=df.lat.values)
df[['u', 'v', 'key']] = pd.DataFrame(list(nearest), index=df.index)

df['severity'] = 1 + 5 * df.NumberKilled + 2 * df.NumberInjured
df['seg'] = [tuple(sorted((u, v))) for u, v in zip(df.u, df.v)]
seg_risk = df.groupby('seg').severity.sum()

edges = ox.graph_to_gdfs(G, nodes=False).reset_index()
edges['seg'] = [tuple(sorted((u, v))) for u, v in zip(edges.u, edges.v)]
edges['risk'] = edges.seg.map(seg_risk).fillna(0)

nx.set_edge_attributes(G, {(r.u, r.v, r.key): r.risk for r in edges.itertuples()}, 'risk')


def set_costs(k):
    nx.set_edge_attributes(
        G,
        {(r.u, r.v, r.key): r.length + k * r.risk for r in edges.itertuples()},
        'safe_cost',
    )


def route_stats(g, r, name):
    length_km = nx.path_weight(g, r, 'length') / 1000
    total_risk = sum(min(d['risk'] for d in g[u][v].values()) for u, v in zip(r[:-1], r[1:]))
    print(f'{name:10s} {length_km:6.1f} km | total crash risk: {total_risk:.0f}')


seed = random.randint(0, 9999)
random.seed(seed)
print('seed:', seed)

while True:
    a, b = df.sample(2, random_state=random.randint(0, 10**6)).itertuples()
    start = ox.distance.nearest_nodes(G, X=a.long, Y=a.lat)
    dest = ox.distance.nearest_nodes(G, X=b.long, Y=b.lat)

    if start == dest or not nx.has_path(G, start, dest):
        continue

    route = nx.shortest_path(G, start, dest, weight='length')
    if len(route) < 15:
        continue

    route_edges = set(zip(route[:-1], route[1:]))
    mask = [(u, v) in route_edges or (v, u) in route_edges for u, v in zip(df.u, df.v)]
    on_route = df[mask]

    if not on_route.empty:
        break

incident = on_route.sample(1, random_state=seed).iloc[0]

route_stats(G, route, 'Fastest')
for k in [10, 25, 50, 100, 250, 500, 1000]:
    set_costs(k)
    sr = nx.shortest_path(G, start, dest, weight='safe_cost')
    route_stats(G, sr, f'k={k}')

K = 100
set_costs(K)
safe_route = nx.shortest_path(G, start, dest, weight='safe_cost')
route_stats(G, safe_route, 'Safest')
print('Same route?', route == safe_route)

G_block = G.copy()
for x, y in [(incident.u, incident.v), (incident.v, incident.u)]:
    if G_block.has_edge(x, y):
        G_block.remove_edges_from([(x, y, key) for key in list(G_block[x][y])])

try:
    detour = nx.shortest_path(G_block, start, dest, weight='safe_cost')
    route_stats(G_block, detour, 'Detour')
except nx.NetworkXNoPath:
    detour = None
    print('No detour exists around this incident. Rerun for a new scenario.')

coords_rad = np.radians(df[['lat', 'long']].values)
db = DBSCAN(eps=0.5 / 6371, min_samples=15, metric='haversine').fit(coords_rad)
df['cluster'] = db.labels_

hotspots = (
    df[df.cluster >= 0]
    .groupby('cluster')
    .agg(
        crashes=('IncidentID', 'count'),
        severity=('severity', 'sum'),
        lat=('lat', 'mean'),
        long=('long', 'mean'),
    )
    .sort_values('severity', ascending=False)
)
print(f'{len(hotspots)} hotspots found')
print(hotspots.head(10))


def coords(r):
    return [(G.nodes[n]['y'], G.nodes[n]['x']) for n in r]


start_pt = coords([start])[0]
dest_pt = coords([dest])[0]

m = folium.Map(
    location=[(start_pt[0] + dest_pt[0]) / 2, (start_pt[1] + dest_pt[1]) / 2],
    zoom_start=10,
    tiles='CartoDB positron',
)

folium.PolyLine(coords(route), color='blue', weight=5, opacity=0.8,
                tooltip='Fastest route').add_to(m)
folium.PolyLine(coords(safe_route), color='green', weight=5, opacity=0.8,
                tooltip='Safest route').add_to(m)
if detour:
    folium.PolyLine(coords(detour), color='orange', weight=5, opacity=0.9,
                    dash_array='8', tooltip='Detour around incident').add_to(m)

folium.Marker(start_pt, tooltip='Start', icon=folium.Icon(color='green')).add_to(m)
folium.Marker(dest_pt, tooltip='Destination', icon=folium.Icon(color='black')).add_to(m)
folium.Marker(
    [incident.lat, incident.long],
    tooltip='Incident',
    popup=f'{incident.CollisionDate} | injured: {incident.NumberInjured} | killed: {incident.NumberKilled}',
    icon=folium.Icon(color='red', icon='exclamation-sign'),
).add_to(m)

for _, h in hotspots.head(15).iterrows():
    folium.Circle(
        location=[h.lat, h.long],
        radius=500,
        color='red',
        fill=True,
        fill_opacity=0.25,
        tooltip=f'Hotspot: {int(h.crashes)} crashes, severity {int(h.severity)}',
    ).add_to(m)

map_file = Path('route_map.html').resolve()
m.save(str(map_file))
webbrowser.open(map_file.as_uri())