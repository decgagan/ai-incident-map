"""Estimate a map position for each incident. Tiers: place (spaCy place name -> Nominatim, within the stated country),
hq (main organisation's HQ from Wikidata, same country), country (country centre).
Requests are cached in data/geocache.json (Nominatim responses by URL, slim Wikidata facts by id), so reruns are fast.
Nominatim (max 1 req/s) and Wikidata lookups run in two threads; a full first run over ~7.7k incidents takes
about an hour; later runs only place new incidents."""
import json, time, re, os, urllib.request, urllib.parse, collections, threading, spacy
UA="ai-incident-map-prototype/0.1 (non-commercial student portfolio)"
NOM_CACHED_ONLY=bool(os.environ.get('NOM_CACHED_ONLY'))  # skip uncached place lookups (fall back to HQ/country)
CACHE='data/geocache.json'; cache=json.load(open(CACHE)) if os.path.exists(CACHE) else {}
# drop full Wikidata entity dumps cached by older versions (they made the cache huge)
for k in [k for k in cache if 'Special:EntityData' in k or 'wikidata.org/w/api.php' in k]: del cache[k]
lock=threading.Lock(); last=collections.defaultdict(float); _n=[0]
def save(force=False):
    with lock:
        _n[0]+=1
        if force or _n[0]%50==0:
            json.dump(cache,open(CACHE+'.tmp','w')); os.replace(CACHE+'.tmp',CACHE)
hostlock=collections.defaultdict(threading.Lock)
def get(url, host, polite):
    # space request *starts* `polite` seconds apart per host (Nominatim policy: at most 1 request/second)
    with hostlock[host]:
        w=polite-(time.time()-last[host])
        if w>0: time.sleep(w)
        last[host]=time.time()
    for i in range(5):
        try:
            r=urllib.request.Request(url,headers={"User-Agent":UA}); res=json.loads(urllib.request.urlopen(r,timeout=30).read()); break
        except Exception:
            if i==4: raise
            time.sleep(5*(i+1))
    return res
def nom(q, cc=None, **kw):
    p=dict(q=q,format='jsonv2',limit=1,addressdetails=1,**kw)
    if cc: p['countrycodes']=cc
    url='https://nominatim.openstreetmap.org/search?'+urllib.parse.urlencode(p)
    if url not in cache:
        if NOM_CACHED_ONLY and not kw: return None
        r=get(url,'nom',1.1)
        with lock: cache[url]=r
        save()
    r=cache[url]; return r[0] if r else None
def wd_search(org):
    k='wds:'+org
    if k not in cache:
        r=get('https://www.wikidata.org/w/api.php?'+urllib.parse.urlencode(dict(action='wbsearchentities',search=org,language='en',format='json',limit=1,type='item')),'wd',0.05)
        with lock: cache[k]=r['search'][0]['id'] if r.get('search') else None
        save()
    return cache[k]
def wd_ents(ids):
    """Fetch slim facts (label, HQ, coords, country, ISO code) for many ids, 50 per request."""
    need=sorted({i for i in ids if i and 'wde:'+i not in cache})
    for j in range(0,len(need),50):
        r=get('https://www.wikidata.org/w/api.php?'+urllib.parse.urlencode(dict(action='wbgetentities',ids='|'.join(need[j:j+50]),props='claims|labels',languages='en',format='json')),'wd',0.05)
        for q,e in r.get('entities',{}).items():
            def c(p):
                try: return e['claims'][p][0]['mainsnak']['datavalue']['value']
                except Exception: return None
            co=c('P625'); hq=c('P159'); ct=c('P17')
            with lock: cache['wde:'+q]=dict(l=e.get('labels',{}).get('en',{}).get('value','?'),hq=hq and hq.get('id'),co=co and [co['latitude'],co['longitude']],c=ct and ct.get('id'),iso=c('P297'))
        save()
def ent(q): return cache.get('wde:'+q) if q else None

nlp=spacy.load('en_core_web_sm',disable=['parser','lemmatizer'])
d=json.load(open('data/incidents.json'))
# records already placed by an earlier run keep their position (set REGEO=1 to redo them all)
if os.environ.get('REGEO'):
    for o in d: o.pop('geo',None)
todo=[o for o in d if 'geo' not in o]
print(len(todo),'of',len(d),'incidents to geolocate',flush=True)
cinfo={}
for c in sorted({o['country'] for o in d if o['country']}):
    r=nom(re.sub(r'\s*\(.*?\)','',c), featuretype='country')
    if not r: print('no country match:',c); continue
    cinfo[c]=dict(cc=r['address'].get('country_code'),lat=float(r['lat']),lon=float(r['lon']),names={c.lower(),r['name'].lower()})
ALLC={'russia','israel','ukraine','china','united states','iran','north korea','gaza','taiwan','india','japan','centre','center','gemini','grok','claude'}
DEMONYM_SKIP={'us','u.s.','usa','uk','eu','europe','america','west','asia','africa','the united states','the uk','the us'}
GOOD={'city','town','village','suburb','municipality','administrative','state','province','county','borough','hamlet','region','quarter','neighbourhood','island'}
ATYPES=('city','town','village','municipality','state','province','region','county','suburb','borough','city_district','district','quarter','island','state_district')
def org_list(o):
    if not o['organisation']: return []
    parts=o['organisation'].split(' , ')
    orgs=[re.sub(r'\s*\(.*?\)','',x).strip() for x in parts]
    roles=[re.search(r'\((.*?)\)',x).group(1) if '(' in x else '' for x in parts]
    return [org for org,role in sorted(zip(orgs,roles),key=lambda t: t[1]!='subject') if role!='mentioned' and org]
texts=[o['title']+'. '+o['summary'][:700] for o in todo]
for o,doc in zip(todo,nlp.pipe(texts,batch_size=64)):
    ci=cinfo.get(o['country']); ents=[]
    for e in doc.ents:
        n=e.text.strip().removeprefix('the ').strip()
        if e.label_ in('GPE','LOC','FAC') and len(n)>2 and not n.isupper() and not n.endswith(('ian','ese','ish')) and n.lower() not in ALLC and n.lower() not in DEMONYM_SKIP and not (ci and n.lower() in ci['names']) and n not in ents: ents.append(n)
    o['place_candidates']=ents
print('places parsed', flush=True)
def place_of(o):
    ci=cinfo.get(o['country']); cc=ci['cc'] if ci else None
    for n in o['place_candidates']:
        try: r=nom(n,cc)
        except Exception: r=None
        if r and (r.get('category') in('place','boundary') or r.get('type') in GOOD) and r.get('addresstype')!='country' and float(r.get('importance') or 0)>=0.45 and r.get('addresstype') in ATYPES:
            return dict(precision='place',lat=float(r['lat']),lon=float(r['lon']),matched=n,resolved=r['display_name'][:90])
def nom_worker():
    for i,o in enumerate(todo):
        o['_place']=place_of(o)
        if i%250==0: print('nominatim',i,'/',len(todo),flush=True)
def wd_worker():
    orgs=sorted({org for o in todo for org in org_list(o)})
    def part(j):
        for i in range(j,len(orgs),2):
            try: wd_search(orgs[i])
            except Exception: pass
            if i%500==0: print('wikidata search',i,'/',len(orgs),flush=True)
    ws=[threading.Thread(target=part,args=(j,)) for j in (0,1)]
    for t in ws: t.start()
    for t in ws: t.join()
    qs=[cache.get('wds:'+org) for org in orgs]; wd_ents(qs)
    wd_ents([ent(q)['hq'] for q in qs if ent(q)]);
    hqs=[ent(ent(q)['hq']) for q in qs if ent(q) and ent(q)['hq']]
    wd_ents([h['c'] for h in hqs if h]); print('wikidata done',flush=True)
ts=[threading.Thread(target=nom_worker),threading.Thread(target=wd_worker)]
for t in ts: t.start()
for t in ts: t.join()
def hq(org, cc):
    e=ent(cache.get('wds:'+org))
    if not e or not e['hq']: return None
    le=ent(e['hq'])
    if not le or not le['co']: return None
    if cc and le['c']:
        ce=ent(le['c'])
        if ce and ce['iso'] and ce['iso'].lower()!=cc: return None
    return dict(lat=le['co'][0],lon=le['co'][1],place=f"{org} HQ: {le['l']}")
for o in todo:
    ci=cinfo.get(o['country']); cc=ci['cc'] if ci else None
    o['geo']=o.pop('_place',None)
    if not o['geo']:
        for org in org_list(o):
            h=hq(org,cc)
            if h: o['geo']=dict(precision='hq',lat=h['lat'],lon=h['lon'],matched=org,resolved=h['place']); break
    if not o['geo'] and ci:
        o['geo']=dict(precision='country',lat=ci['lat'],lon=ci['lon'],matched=o['country'],resolved=o['country'])
save(True)
json.dump(d,open('data/incidents.json','w'),indent=1,ensure_ascii=False)
print(collections.Counter(o['geo']['precision'] if o['geo'] else 'none' for o in d))
