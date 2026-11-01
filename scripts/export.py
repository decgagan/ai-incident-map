"""Write the files the web app loads: web/public/incidents.json (one light record per mapped incident) and
web/public/summaries/<n>.json (summaries in chunks of 200, fetched only when a point is opened)."""
import json, os, glob
d = json.load(open('data/incidents.json'))
d = sorted((o for o in d if o.get('geo')), key=lambda o: (o['date'] or '', o['id']), reverse=True)
CH = 200
out = [dict(id=o['id'], title=o['title'], date=(o['date'] or '')[:10], status=o['evidence_status'], category=o['category'],
            country=o['country'], url=o['url'], kind=o['kind'], lat=round(o['geo']['lat'], 3), lon=round(o['geo']['lon'], 3),
            precision=o['geo']['precision'], place=o['geo']['resolved'], s=i // CH) for i, o in enumerate(d)]
json.dump(out, open('web/public/incidents.json', 'w'), ensure_ascii=False, separators=(',', ':'))
os.makedirs('web/public/summaries', exist_ok=True)
for f in glob.glob('web/public/summaries/*.json'): os.remove(f)
for j in range(0, len(d), CH):
    json.dump({o['id']: o['summary'] for o in d[j:j + CH]}, open(f'web/public/summaries/{j // CH}.json', 'w'), ensure_ascii=False, separators=(',', ':'))
print('exported', len(out), 'of', json.load(open('data/incidents.json')).__len__(), 'incidents;', -(-len(out) // CH), 'summary chunks')
