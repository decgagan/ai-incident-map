"""Polite scrape of the newest incident pages from aiincidentindex.com (sitemap + HTML pages, ~1 req/s, cached in data/raw/, never touches /api/)."""
import re, json, time, html, urllib.request, os
UA="ai-incident-map-prototype/0.1 (non-commercial student portfolio; respects robots.txt)"
def get(u,tries=5):
    for i in range(tries):
        try:
            r=urllib.request.Request(u,headers={"User-Agent":UA}); return urllib.request.urlopen(r,timeout=30).read().decode()
        except Exception:
            if i==tries-1: raise
            time.sleep(5*(i+1))
N=int(os.environ.get('N_INCIDENTS','0')) or 10**9  # 0/unset = every incident
# sitemap index lists one sitemap per year; each is newest-first
years=sorted(re.findall(r'incidents-(\d{4})\.xml',get('https://www.aiincidentindex.com/sitemap.xml')),reverse=True)
urls=[]
for y in years:
    urls+=re.findall(r'<loc>(.*?)</loc>',get(f'https://www.aiincidentindex.com/sitemaps/incidents-{y}.xml')); time.sleep(1.1)
    if len(urls)>=N: break
urls=urls[:N]
os.makedirs('data/raw',exist_ok=True)
def txt(s): return html.unescape(re.sub(r'\s+',' ',re.sub(r'<[^>]+>',' ',s))).strip()
LABELS=["Organizations","Organization","Category","Industry","Country","Harm status","Intent","Timing","Harm types","Failure modes","Consequences","AI systems","Regulations"]
out=[]
# earlier results: lets a fresh checkout (e.g. GitHub Actions, no data/raw cache) skip pages it already has
prev={o['url']:o for o in json.load(open('data/incidents.json'))} if os.path.exists('data/incidents.json') else {}
for u in urls:
    slug=u.rsplit('/',1)[1]; p=f'data/raw/{slug}.html'
    if not os.path.exists(p) and u in prev and 'geo' in prev[u]: out.append(prev[u]); continue
    if not os.path.exists(p):
        h=get(u); open(p,'w').write(h); time.sleep(1.1)
    h=open(p).read()
    if not re.search(r'AII-\d+-\d+',h): print('skip (no id)',slug); continue
    h2=re.sub(r'(?s)<(script|style)[^>]*>.*?</\1>','',h)
    m=re.search(r'(?s)<main.*?</main>',h2); t=txt(m.group(0) if m else h2)
    ld=[json.loads(x) for x in re.findall(r'<script type="application/ld\+json">(.*?)</script>',h)]
    art=next((x for x in ld if x.get('@type')=='Article'),{})
    cls=t.split(' Classification ',1)[1] if ' Classification ' in t else t
    f={}
    pat='('+'|'.join(map(re.escape,LABELS))+r') '
    parts=re.split(pat,cls.split(' Sources and evidence')[0])
    for i in range(1,len(parts)-1,2): f.setdefault(parts[i],parts[i+1].strip())
    # organisation names can contain a label word ("Lancaster Country Day School"), so take the whole
    # Organizations block up to Category, and the last Country field, cut at any trailing page text
    mo=re.search(r'Organizations? (.*?) Category ',cls)
    if mo: f['Organizations']=mo.group(1).strip()
    cs=[parts[i+1].strip() for i in range(1,len(parts)-1,2) if parts[i]=='Country']
    if cs: f['Country']=re.split(r' (?:Date|Drafted by|What happened|Sources) ',cs[-1])[0].strip()
    wh=re.search(r' What happened (.*?) Classification ',t)
    status=re.search(r'AII-[\d-]+ Incidents / [^/]+? (Confirmed|Well documented|Reported|Under investigation|Alleged) ',t)
    out.append(dict(id=art.get('identifier') or re.search(r'AII-\d+-\d+',t).group(0),
      title=art.get('headline'),summary=(wh.group(1) if wh else art.get('description','')),
      date=art.get('datePublished'),evidence_status=status.group(1) if status else None,
      category=f.get('Category'),organisation=f.get("Organizations") or f.get("Organization"),country=f.get('Country'),url=u,harm_status=f.get('Harm status'),intent=f.get('Intent'),harm_types=f.get('Harm types'),consequences=f.get('Consequences'),industry=f.get('Industry')))
    if u in prev and 'geo' in prev[u] and prev[u]['id']==out[-1]['id']:
        for k in ('geo','place_candidates'): out[-1][k]=prev[u].get(k)
json.dump(out,open('data/incidents.json','w'),indent=1,ensure_ascii=False)
print('scraped',len(out))
