"""Descarga reproducible, extracto con vías completas y manifiesto de procedencia."""
import datetime
import hashlib
import json
import os
from pathlib import Path
import subprocess

root = Path('/data')
root.mkdir(exist_ok=True)
source = os.getenv('OSM_PBF_URL', 'https://download.geofabrik.de/south-america/colombia-latest.osm.pbf')
bbox = os.getenv('ROUTING_BBOX', '-74.28,11.12,-74.05,11.36')
manifest = root / 'source.json'
if (root / 'santa-marta.osm.pbf').exists() and manifest.exists():
    previous = json.loads(manifest.read_text())
    if previous['source'] != source or previous['bbox'] != bbox:
        raise SystemExit('La fuente/cobertura cambió; usar otro volumen para regenerar datos explícitamente')
    print('Extracto existente; se conserva sin regenerar')
    raise SystemExit(0)
pbf = root / 'source.osm.pbf'
subprocess.run(['curl', '--fail', '--location', '--retry', '3', '--output', str(pbf), source], check=True)
subprocess.run(['osmium', 'extract', '--bbox', bbox, '--strategy', 'complete_ways', str(pbf), '-o', str(root / 'santa-marta.osm.pbf'), '--overwrite'], check=True)
metadata = subprocess.check_output(['osmium', 'fileinfo', '-e', '-j', str(pbf)], text=True)
manifest.write_text(json.dumps({'source':source, 'downloadedAt':datetime.datetime.now(datetime.timezone.utc).isoformat(),
    'bbox':bbox, 'license':'ODbL-1.0', 'attribution':'© OpenStreetMap contributors / Geofabrik',
    'sha256':hashlib.file_digest(pbf.open('rb'), 'sha256').hexdigest(), 'metadata':json.loads(metadata)}, indent=2))
print('Extracto preparado y procedencia registrada en source.json')
