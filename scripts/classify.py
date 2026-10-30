"""Label each incident 'event' (real-world harm/event) or 'research' (study, policy, warning, announcement).
Transparent rule: score = research keywords - event keywords + 1 if 'Potential harm' - 1 if 'Actual harm'
score >= 1 AND at least one research keyword -> research. The reason is stored with each record."""
import json, re
RESEARCH = r"\b(stud(y|ies)|researchers?|research|experiment|simulat\w*|sandbox|benchmark|report(s|ed)? (finds?|shows?|warns?)|survey|analysis|warns?|calls? for|urges?|regulat\w*|legislat\w*|bill|law|policy|guidelines?|framework|ombudsman|commits?|discloses?|announces?|approves?|considers?|plans?|proposal|tests?|testing|security test|evaluation|red[- ]team\w*|preference|fails? to regulate)\b"
EVENT = r"\b(sue[sd]?|lawsuit|fined?|arrest\w*|charged|charges|prosecut\w*|convicted|breach\w*|hack\w*|stole|steal\w*|scam\w*|fraud\w*|crash\w*|died|dies|death|killed|injur\w*|victims?|deceived|sho(o)?t down|recruit\w*|police report|failures?|destroy\w*|leak\w*|exposed?|spread\w*|circulat\w*|viral|targets?|targeted|deepfakes? (of|video)|lays? off|cuts? \d+|insult\w*|malfunction\w*|bans?|block(s|ed)|removal|dismantle\w*|campaigns?|uploaded)\b"
def classify(o):
    t = (o['title'] + '. ' + (o.get('summary') or '')[:400]).lower()
    r = sorted(set(m.group(0) for m in re.finditer(RESEARCH, t)))
    e = sorted(set(m.group(0) for m in re.finditer(EVENT, t)))
    score = len(r) - len(e)
    score += 1 if o.get('harm_status') == 'Potential harm' else -1 if o.get('harm_status') == 'Actual harm' else 0
    label = 'research' if (score >= 1 and r) else 'event'
    return label, f"score {score}: research[{', '.join(r)}] event[{', '.join(e)}] harm={o.get('harm_status')} consequences={o.get('consequences')}"
if __name__ == '__main__':
    d = json.load(open('data/incidents.json'))
    for o in d: o['kind'], o['kind_reason'] = classify(o)
    json.dump(d, open('data/incidents.json', 'w'), indent=1, ensure_ascii=False)
    print(sum(o['kind'] == 'research' for o in d), 'research of', len(d))
