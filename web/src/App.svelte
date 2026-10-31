<script>
  import { onMount } from 'svelte'
  import { geoNaturalEarth1, geoPath, geoGraticule10 } from 'd3-geo'
  import { zoom as d3zoom, zoomIdentity } from 'd3-zoom'
  import { select } from 'd3-selection'
  import { feature, mesh } from 'topojson-client'
  import Matrix from './Matrix.svelte'

  let W = $state(960), H = $state(500), topo = null, raw = [], box
  let proj = $state(geoNaturalEarth1()), land = $state(''), borders = $state(''), sphere = $state(''), grat = $state('')
  let incidents = $state([]), filter = $state('All'), hideResearch = $state(false), sel = $state(null), k = $state(1), svg, zoomer

  const HACK = 'Security and cyberattacks'
  const short = (c) => c === HACK ? 'Hacking' : c?.split(/,| and /)[0]
  const pool = $derived(hideResearch ? incidents.filter(d => d.kind === 'event') : incidents)
  const cats = $derived(['All', HACK, ...[...new Set(incidents.map(d => d.category))].filter(c => c && c !== HACK).sort()])
  const counts = $derived(Object.fromEntries(cats.map(c => [c, c === 'All' ? pool.length : pool.filter(d => d.category === c).length])))
  const shown = $derived(filter === 'All' ? pool : pool.filter(d => d.category === filter))
  const nResearch = $derived(incidents.filter(d => d.kind === 'research').length)

  // golden-angle spiral jitter so stacked points spread out
  function place(list, p) {
    const groups = {}
    return list.map(d => {
      const [x, y] = p([d.lon, d.lat]); const key = Math.round(x / 3) + ',' + Math.round(y / 3)
      const n = groups[key] = (groups[key] ?? -1) + 1
      const r = n ? 3.2 * Math.sqrt(n) : 0, a = n * 2.39996
      return { ...d, x: x + r * Math.cos(a), y: y + r * Math.sin(a) }
    })
  }
  // inhabited latitudes only, so the map isn't mostly ice
  const frame = { type: 'Polygon', coordinates: [[[-180, -56], [180, -56], [180, 78], [-180, 78], [-180, -56]].reverse()] }

  function layout() {
    if (!topo || !box) return
    const cw = box.clientWidth, ch = box.clientHeight
    W = cw; H = ch
    const portrait = ch > cw * 0.8
    const p = geoNaturalEarth1()
    if (portrait) {
      // fit to height: the world is wider than the screen, so pan sideways
      p.fitHeight(ch - 8, frame)
      const [[x0], [x1]] = geoPath(p).bounds(frame)
      p.translate([p.translate()[0] - x0 + 4, p.translate()[1]])
    } else p.fitExtent([[6, 6], [cw - 6, ch - 6]], frame)
    proj = p
    const path = geoPath(p)
    const countries = feature(topo, topo.objects.countries)
    countries.features = countries.features.filter(f => f.id !== '010')
    land = path(countries); borders = path(mesh(topo, topo.objects.countries, (a, b) => a !== b))
    sphere = path({ type: 'Sphere' }); grat = path(geoGraticule10())
    incidents = place(raw, p)
    const [[bx0, by0], [bx1, by1]] = path.bounds(frame)
    zoomer = d3zoom().scaleExtent([1, 12]).translateExtent([[Math.min(0, bx0), Math.min(0, by0)], [Math.max(cw, bx1), Math.max(ch, by1)]])
      .on('zoom', e => { select(svg).select('g.zoom').attr('transform', e.transform); k = e.transform.k })
    select(svg).call(zoomer).on('dblclick.zoom', null)
    // portrait: start centred on Europe/Africa
    const t = portrait ? zoomIdentity.translate(cw / 2 - p([12, 30])[0], 0) : zoomIdentity
    select(svg).call(zoomer.transform, t)
  }

  onMount(() => {
    Promise.all([fetch('/countries-110m.json').then(r => r.json()), fetch('/incidents.json').then(r => r.json())]).then(([t, inc]) => {
      topo = t; raw = inc.sort((a, b) => a.date < b.date ? 1 : -1); layout()
    })
    let to; const ro = new ResizeObserver(() => { clearTimeout(to); to = setTimeout(layout, 150) }); ro.observe(box)
    return () => ro.disconnect()
  })
  const fmt = (s) => new Date(s).toLocaleDateString('en-GB', { day: 'numeric', month: 'short', year: 'numeric' })
  const onKey = (e) => e.key === 'Escape' && (sel = null)
</script>

<svelte:window onkeydown={onKey} />
<Matrix />
<main>
  <header>
    <h1>&gt; AI_INCIDENT_MAP<span class="cur">_</span></h1>
    <p>{shown.length} of {incidents.length} most recent incidents · <span class="legend">fewer <span class="ramp"></span> more incidents</span> · <span class="key dot"></span> place / HQ <span class="key ring"></span> country only</p>
  </header>
  <label class="toggle" class:on={hideResearch}>
    <input type="checkbox" bind:checked={hideResearch} onchange={() => sel = null} />
    <span class="sw" aria-hidden="true"></span> Hide research &amp; policy news <small>({hideResearch ? `${nResearch} hidden` : `${nResearch} shown`})</small>
  </label>
  <nav aria-label="Category filter">
    {#each cats as c}
      <button class:on={filter === c} onclick={() => { filter = c; sel = null }}>{c === 'All' ? 'All' : short(c)} <small>{counts[c]}</small></button>
    {/each}
  </nav>
  <div class="map" bind:this={box}>
    <svg bind:this={svg} viewBox="0 0 {W} {H}" width={W} height={H} role="img" aria-label="World map of AI incidents" onclick={(e) => e.target === svg && (sel = null)}>
      <defs><radialGradient id="heat"><stop offset="0" stop-color="#ff5a1e" stop-opacity=".55"/><stop offset=".35" stop-color="#e01010" stop-opacity=".3"/><stop offset="1" stop-color="#600" stop-opacity="0"/></radialGradient><filter id="glow" x="-50%" y="-50%" width="200%" height="200%"><feGaussianBlur stdDeviation="2" result="b"/><feMerge><feMergeNode in="b"/><feMergeNode in="SourceGraphic"/></feMerge></filter></defs>
      <g class="zoom">
        <path class="sphere" d={sphere} />
        <path class="grat" d={grat} />
        <path class="land" d={land} />
        <path class="borders" d={borders} />
        <g class="heat" style="isolation:isolate">
          {#each shown as d (d.id)}<circle cx={d.x} cy={d.y} r={(d.precision === 'country' ? 30 : 22) / Math.sqrt(k)} fill="url(#heat)" />{/each}
        </g>
        {#each shown as d (d.id)}
          <g class="pt {d.precision}" class:active={sel?.id === d.id} transform="translate({d.x},{d.y}) scale({1 / Math.sqrt(k)})"
             role="button" tabindex="0" aria-label={d.title}
             onclick={(e) => { e.stopPropagation(); sel = d }} onkeydown={(e) => e.key === 'Enter' && (sel = d)}>
            <circle r="9" class="hit" />
            {#if d.precision === 'country'}<circle r="2.6" class="ring" style="opacity:{Math.min(1, .35 + k / 5)}" />{:else}<circle r="1.8" class="dot" style="opacity:{Math.min(1, .45 + k / 5)}" />{/if}
          </g>
        {/each}
      </g>
    </svg>
  </div>
  {#if sel}
    <aside class="pop" aria-live="polite">
      <button class="x" aria-label="Close" onclick={() => sel = null}>×</button>
      <div class="meta">{#if sel.kind === 'research'}<span class="rk">RESEARCH / POLICY</span> · {/if}{fmt(sel.date)} · <span class="tag">{short(sel.category)}</span> · <span class="st">{sel.status}</span></div>
      <h2>{sel.title}</h2>
      <p class="sum">{sel.summary}</p>
      <div class="loc">📍 {sel.precision === 'place' ? sel.place.split(',').slice(0,2).join(',') : sel.precision === 'hq' ? sel.place : sel.country + ' (country only)'}</div>
      <a href={sel.url} target="_blank" rel="noopener">{sel.id} ↗</a>
    </aside>
  {/if}
  <footer>Data: <a href="https://www.aiincidentindex.com/data" target="_blank" rel="noopener">AI Incident Index</a> (<a href="https://creativecommons.org/licenses/by/4.0/" target="_blank" rel="noopener">CC BY 4.0</a>) · locations estimated from text, not from the Index · prototype</footer>
</main>

<style>
  main{position:relative;z-index:1;height:100%;display:flex;flex-direction:column;padding:12px 16px;gap:8px}
  h1{margin:0;font-size:clamp(18px,3vw,26px);color:var(--g);text-shadow:0 0 8px var(--g);letter-spacing:.06em}
  header p{margin:2px 0 0;font-size:12px;color:#7fd99a}
  .cur{animation:b 1s steps(1) infinite}@keyframes b{50%{opacity:0}}
  nav{display:flex;gap:6px;overflow-x:auto;padding-bottom:2px;scrollbar-width:thin}
  nav button{flex:none;background:rgba(2,12,5,.85);color:#9ff0b4;border:1px solid var(--gd);padding:5px 9px;font:inherit;font-size:12px;cursor:pointer;border-radius:3px}
  nav button.on{background:var(--g);color:#021;border-color:var(--g);box-shadow:0 0 10px var(--g)}
  nav small{opacity:.7}
  .map{flex:1;min-height:0;position:relative;overflow:hidden}
  svg{width:100%;height:100%;display:block;cursor:grab;touch-action:none}
  .sphere{fill:rgba(1,10,4,.75);stroke:var(--gd);stroke-width:.6}
  .grat{fill:none;stroke:#0c3a19;stroke-width:.4}
  .land{fill:#06240f;stroke:none}
  .borders{fill:none;stroke:#1d6b35;stroke-width:.4}
  .pt{cursor:pointer}.hit{fill:transparent}
  .heat circle{mix-blend-mode:plus-lighter;pointer-events:none}
  .dot{fill:#ffd2b0}
  .ring{fill:rgba(255,80,40,.15);stroke:#ff8a6a;stroke-width:.8;stroke-dasharray:1.5 1.2}
  .legend{white-space:nowrap}.ramp{display:inline-block;width:70px;height:8px;vertical-align:middle;margin:0 4px;border-radius:4px;background:linear-gradient(90deg,#300,#b00,#ff3a10,#ffb070,#fff4e8)}
  .pt.active .dot,.pt.active .ring{fill:#fff;stroke:#fff}
  .pt:focus{outline:none}.pt:focus-visible .hit{stroke:#fff;stroke-width:.8}
  .pop{position:absolute;right:16px;top:110px;width:min(380px,calc(100% - 32px));max-height:calc(100% - 160px);overflow:auto;background:rgba(1,12,5,.95);border:1px solid var(--g);box-shadow:0 0 18px rgba(57,255,106,.35);padding:14px 16px;border-radius:4px;font-size:13px;line-height:1.45}
  .pop h2{font-size:15px;margin:6px 0;color:#eafff0}
  .meta{font-size:11px;color:#8be3a3}.tag{color:var(--g)}.st{border:1px solid var(--gd);padding:0 4px}
  .sum{color:#bfe9cb;margin:6px 0 8px}.loc{font-size:11px;color:#8be3a3;margin-bottom:6px}
  .x{position:absolute;right:6px;top:4px;background:none;border:0;color:var(--g);font-size:20px;cursor:pointer}
  .key{display:inline-block;width:8px;height:8px;border-radius:50%;margin:0 2px 0 6px;vertical-align:middle}.key.dot{background:#ffd2b0;box-shadow:0 0 6px #f40}.key.ring{border:1px dashed #ff8a6a}
  .toggle{display:inline-flex;align-items:center;gap:8px;font-size:13px;color:#c9ffd6;cursor:pointer;align-self:flex-start;border:1px solid var(--gd);padding:5px 10px;border-radius:3px;background:rgba(2,12,5,.85)}
  .toggle.on{border-color:var(--g);box-shadow:0 0 8px rgba(57,255,106,.5)}
  .toggle input{position:absolute;opacity:0;width:1px;height:1px}.toggle:focus-within{outline:1px solid #fff}
  .sw{width:30px;height:16px;border-radius:8px;background:#0c3a19;position:relative;flex:none}.sw::after{content:'';position:absolute;left:2px;top:2px;width:12px;height:12px;border-radius:50%;background:#5fd47e;transition:left .15s}
  .toggle.on .sw{background:var(--g)}.toggle.on .sw::after{left:16px;background:#021}
  .toggle small{color:#7fd99a}.rk{color:#ffd76a}
  footer{font-size:11px;color:#7fd99a}
  @media (max-width:640px){.pop{top:auto;bottom:34px;right:8px;left:8px;width:auto;max-height:48%}main{padding:10px}}
</style>
