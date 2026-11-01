"""Monthly refresh: scrape -> geolocate -> classify -> export web/public/incidents.json.
Run from the repo root:  python scripts/refresh.py   (every incident by default; N_INCIDENTS=100 for just the newest 100)"""
import subprocess, sys
for step in ['scrape', 'geolocate', 'classify', 'export']:
    print('==', step, flush=True)
    subprocess.run([sys.executable, f'scripts/{step}.py'], check=True)
