"""Monthly refresh: scrape -> geolocate -> classify -> export web/public/incidents.json.
Run from the repo root:  python scripts/refresh.py   (N_INCIDENTS=100 by default)"""
import subprocess, sys
for step in ['scrape', 'geolocate', 'classify', 'export']:
    print('==', step, flush=True)
    subprocess.run([sys.executable, f'scripts/{step}.py'], check=True)
