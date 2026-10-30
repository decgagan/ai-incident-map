"""Write the slim file the web app loads."""
import json
d = json.load(open('data/incidents.json'))
out = [dict(id=o['id'], title=o['title'], summary=o['summary'], date=o['date'], status=o['evidence_status'], category=o['category'],
            country=o['country'], url=o['url'], kind=o['kind'], lat=round(o['geo']['lat'], 4), lon=round(o['geo']['lon'], 4),
            precision=o['geo']['precision'], place=o['geo']['resolved']) for o in d if o.get('geo')]
json.dump(out, open('web/public/incidents.json', 'w'), ensure_ascii=False)
print('exported', len(out))
