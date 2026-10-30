"""Estimate a map position for each incident. Tiers: place (spaCy place name -> Nominatim, within the stated country),
hq (main organisation's HQ from Wikidata, same country), country (country centre). Requests are cached in data/geocache.json."""
import json, time, re, os, urllib.request, urllib.parse, collections, spacy
UA="ai-incident-map-prototype/0.1 (non-commercial student portfolio)"
CACHE='data/geocache.json'; cache=json.load(open(CACHE)) if os.path.exists(CACHE) else {}
last=[0]
def fetch(url, polite=1.1):
    if url in cache: return cache[url]
    w=polite-(time.time()-last[0])
    if w>0: time.sleep(w)
    r=urllib.request.Request(url,headers={"User-Agent":UA}); res=json.loads(urllib.request.urlopen(r,timeout=30).read()); last[0]=time.time()
    cache[url]=res; json.dump(cache,open(CACHE,'w')); return res
def nom(q, cc=None, **kw):
    p=dict(q=q,format='jsonv2',limit=1,addressdetails=1,**kw)
    if cc: p['countrycodes']=cc
    r=fetch('https://nominatim.openstreetmap.org/search?'+urllib.parse.urlencode(p)); return r[0] if r else None
nlp=spacy.load('en_core_web_sm')
d=json.load(open('data/incidents.json'))
# country info
cinfo={}
for c in {o['country'] for o in d if o['country']}:
    r=nom(c, featuretype='country'); cinfo[c]=dict(cc=r['address']['country_code'],lat=float(r['lat']),lon=float(r['lon']),names={c.lower(),r['name'].lower()})
ALLC={'russia','israel','ukraine','china','united states','iran','north korea','gaza','taiwan','india','japan','centre','center','gemini','grok','claude'}
DEMONYM_SKIP={'us','u.s.','usa','uk','eu','europe','america','west','asia','africa','the united states','the uk','the us'}
GOOD={'city','town','village','suburb','municipality','administrative','state','province','county','borough','hamlet','region','quarter','neighbourhood','island'}
def wd(q):
    return fetch('https://www.wikidata.org/w/api.php?'+urllib.parse.urlencode(dict(action='wbsearchentities',search=q,language='en',format='json',limit=1,type='item')),0.3)
def wdent(qid):
    return fetch(f'https://www.wikidata.org/wiki/Special:EntityData/{qid}.json',0.3)['entities'][qid]
def claim(e,p):
    try: return e['claims'][p][0]['mainsnak']['datavalue']['value']
    except Exception: return None
def hq(org, cc):
    s=wd(org).get('search')
    if not s: return None
    e=wdent(s[0]['id']); loc=claim(e,'P159')
    if not loc: return None
    le=wdent(loc['id']); co=claim(le,'P625'); ctry=claim(le,'P17')
    if not co: return None
    if cc and ctry:
        ce=wdent(ctry['id']); iso=claim(ce,'P297')
        if iso and iso.lower()!=cc: return None
    return dict(lat=co['latitude'],lon=co['longitude'],place=f"{org} HQ: {le['labels'].get('en',{}).get('value','?')}")
for o in d:
    ci=cinfo.get(o['country']); cc=ci['cc'] if ci else None
    text=o['title']+'. '+o['summary'][:700]
    ents=[]
    for e in nlp(text).ents:
        n=e.text.strip().removeprefix('the ').strip()
        if e.label_ in('GPE','LOC','FAC') and len(n)>2 and not n.isupper() and not n.endswith(('ian','ese','ish')) and n.lower() not in ALLC and n.lower() not in DEMONYM_SKIP and not (ci and n.lower() in ci['names']) and n not in ents: ents.append(n)
    o['geo']=None
    for n in ents:
        r=nom(n,cc)
        if r and (r.get('category') in('place','boundary') or r.get('type') in GOOD) and r.get('addresstype')!='country' and float(r.get('importance') or 0)>=0.45 and r.get('addresstype') in ('city','town','village','municipality','state','province','region','county','suburb','borough','city_district','district','quarter','island','state_district'):
            o['geo']=dict(precision='place',lat=float(r['lat']),lon=float(r['lon']),matched=n,resolved=r['display_name'][:90]); break
    if not o['geo'] and o['organisation']:
        orgs=[re.sub(r'\s*\(.*?\)','',x).strip() for x in o['organisation'].split(' , ')]
        roles=[re.search(r'\((.*?)\)',x).group(1) if '(' in x else '' for x in o['organisation'].split(' , ')]
        for org,role in sorted(zip(orgs,roles),key=lambda t: t[1]!='subject'):
            if role=='mentioned': continue
            try: h=hq(org,cc)
            except Exception as ex: h=None
            if h: o['geo']=dict(precision='hq',lat=h['lat'],lon=h['lon'],matched=org,resolved=h['place']); break
    if not o['geo'] and ci:
        o['geo']=dict(precision='country',lat=ci['lat'],lon=ci['lon'],matched=o['country'],resolved=o['country'])
    o['place_candidates']=ents
json.dump(d,open('data/incidents.json','w'),indent=1,ensure_ascii=False)
print(collections.Counter(o['geo']['precision'] if o['geo'] else 'none' for o in d))
