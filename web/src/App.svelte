<script>
  import { onMount } from 'svelte'
  import { geoNaturalEarth1, geoPath, geoGraticule10 } from 'd3-geo'
  import { zoom as d3zoom, zoomIdentity } from 'd3-zoom'
  import { select } from 'd3-selection'
  import { feature, mesh } from 'topojson-client'
  import Matrix from './Matrix.svelte'

  let W = $state(960), H = $state(500), topo = null, raw = [], box, svg, cv, zoomer
  let land = $state(''), borders = $state(''), sphere = $state(''), grat = $state('')
  let incidents = $state.raw([]), filter = $state('All'), hideResearch = $state(false), sel = $state(null), summary = $state('')
  let tr = zoomIdentity, hover = $state(false)

  const HACK = 'Security and cyberattacks'
  const short = (c) => c === HACK ? 'Hacking' : c?.split(/,| and /)[0]
  const pool = $derived(hideResearch ? incidents.filter(d => d.kind === 'event') : incidents)
  const cats = $derived(['All', HACK, ...[...new Set(incidents.map(d => d.category))].filter(c => c && c !== HACK).sort()])
  const counts = $derived(Object.fromEntries(cats.map(c => [c, c === 'All' ? pool.length : pool.filter(d => d.category === c).length])))
  const shown = $derived(filter === 'All' ? pool : pool.filter(d => d.category === filter))
  const nResearch = $derived(incidents.filter(d => d.kind === 'research').length)

  // golden-angle spiral so incidents stacked on one spot (e.g. a country centre) spread out and stay clickable when zoomed
  function place(list, p) {
    const groups = {}
    return list.map(d => {
      const [x, y] = p([d.lon, d.lat]); const key = Math.round(x / 2) + ',' + Math.round(y / 2)
      const n = groups[key] = (groups[key] ?? -1) + 1
      const r = n ? 1.6 * Math.sqrt(n) : 0, a = n * 2.39996
      return { ...d, x: x + r * Math.cos(a), y: y + r * Math.sin(a) }
    })
  }
  // inhabited latitudes only, so the map isn't mostly ice
  const frame = { type: 'Polygon', coordinates: [[[-180, -56], [180, -56], [180, 78], [-180, 78], [-180, -56]].reverse()] }

  // ---- canvas layer: binary-digit heat + small glowing dots (fast enough for thousands of points) ----
  const CELL = 4, KR = 5  // tight digit grid; kernel radius in cells keeps the same ~20px spread
  const bit = (a, b) => { let h = Math.imul(a, 374761393) + Math.imul(b, 668265263) | 0; h = Math.imul(h ^ (h >>> 13), 1274126177); return (h ^ (h >>> 16)) & 1 ? '1' : '0' }
  const sprite = (draw, s = 16) => { const c = document.createElement('canvas'); c.width = c.height = s; draw(c.getContext('2d'), s / 2); return c }
  let dotS, ringS, selS
  function sprites() {
    const dpr = devicePixelRatio || 1, s = Math.ceil(16 * dpr)
    dotS = sprite((g, h) => { const r = g.createRadialGradient(h, h, 0, h, h, h); r.addColorStop(0, 'rgba(255,120,105,.95)'); r.addColorStop(.22, 'rgba(240,60,50,.85)'); r.addColorStop(.45, 'rgba(200,30,30,.22)'); r.addColorStop(1, 'rgba(120,0,0,0)'); g.fillStyle = r; g.fillRect(0, 0, 2 * h, 2 * h) }, s)
    ringS = sprite((g, h) => { g.strokeStyle = 'rgba(255,110,100,.75)'; g.lineWidth = dpr; g.setLineDash([1.5 * dpr, 1.2 * dpr]); g.beginPath(); g.arc(h, h, h * .32, 0, 7); g.stroke() }, s)
    selS = sprite((g, h) => { g.fillStyle = '#fff'; g.shadowColor = '#fff'; g.shadowBlur = h * .5; g.beginPath(); g.arc(h, h, h * .3, 0, 7); g.fill() }, s)
  }
  let raf = 0
  const redraw = () => { if (!raf) raf = requestAnimationFrame(draw) }
  function draw() {
    raf = 0
    if (!cv) return
    const dpr = devicePixelRatio || 1, ctx = cv.getContext('2d')
    if (cv.width !== Math.round(W * dpr)) { cv.width = Math.round(W * dpr); cv.height = Math.round(H * dpr) }
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0); ctx.clearRect(0, 0, W, H)
    const { k, x: tx, y: ty } = tr, pts = shown
    const cols = Math.ceil(W / CELL) + 1, rows = Math.ceil(H / CELL) + 1, grid = new Float32Array(cols * rows)
    // anchor the digit grid to the map so digits move with it while panning
    const ox = ((tx % CELL) + CELL) % CELL - CELL, oy = ((ty % CELL) + CELL) % CELL - CELL
    const sx = new Float32Array(pts.length), sy = new Float32Array(pts.length)
    for (let i = 0; i < pts.length; i++) {
      const X = sx[i] = pts[i].x * k + tx, Y = sy[i] = pts[i].y * k + ty
      const c = Math.floor((X - ox) / CELL), r = Math.floor((Y - oy) / CELL)
      for (let dy = -KR; dy <= KR; dy++) for (let dx = -KR; dx <= KR; dx++) {
        const cc = c + dx, rr = r + dy; if (cc < 0 || rr < 0 || cc >= cols || rr >= rows) continue
        grid[rr * cols + cc] += Math.exp(-(dx * dx + dy * dy) / 11) * .2
      }
    }
    let mx = 6; for (let i = 0; i < grid.length; i++) if (grid[i] > mx) mx = grid[i]
    const lm = Math.log1p(mx)
    // soft red under-glow: the density grid scaled up with smoothing
    const im = new ImageData(cols, rows)
    for (let i = 0; i < grid.length; i++) if (grid[i] > 0) { const v = Math.log1p(grid[i]) / lm; im.data[i * 4] = 200 + 40 * v; im.data[i * 4 + 1] = 25 + 30 * v; im.data[i * 4 + 2] = 25; im.data[i * 4 + 3] = 95 * v * v }
    const gc = new OffscreenCanvas(cols, rows); gc.getContext('2d').putImageData(im, 0, 0)
    ctx.save(); ctx.imageSmoothingEnabled = true; ctx.globalCompositeOperation = 'lighter'; ctx.filter = 'blur(5px)'
    ctx.drawImage(gc, ox + CELL / 2, oy + CELL / 2, cols * CELL, rows * CELL); ctx.restore()
    // Matrix-style binary digits, brighter where incidents cluster
    ctx.font = `bold ${CELL + 1.5}px ui-monospace, monospace`; ctx.textAlign = 'center'; ctx.textBaseline = 'middle'
    const gx = Math.round(-tx / CELL), gy = Math.round(-ty / CELL)
    for (let r = 0; r < rows; r++) for (let c = 0; c < cols; c++) {
      const g = grid[r * cols + c]; if (g < .08) continue
      const v = Math.log1p(g) / lm
      ctx.fillStyle = `rgba(${235 + 20 * v | 0},${45 + 120 * v * v | 0},${40 + 90 * v * v | 0},${.12 + .7 * v})`
      ctx.fillText(bit(c + gx, r + gy), ox + c * CELL + CELL / 2, oy + r * CELL + CELL / 2)
    }
    // small dots on top (country-only ones as dashed rings)
    const s = 16 * Math.min(1.8, .75 * Math.pow(k, .3)), h = s / 2
    // normal blending (not additive) so thousands of stacked dots don't burn out to white
    // dots hidden at world view, fade in from 2x zoom, fully visible from 6x (clicks work at every zoom)
    const fade = Math.min(1, Math.max(0, (k - 2) / 4))
    ctx.globalAlpha = .8 * fade * fade * (3 - 2 * fade)
    if (ctx.globalAlpha > 0) for (let i = 0; i < pts.length; i++) {
      const X = sx[i], Y = sy[i]; if (X < -h || Y < -h || X > W + h || Y > H + h) continue
      ctx.drawImage(pts[i].precision === 'country' ? ringS : dotS, X - h, Y - h, s, s)
    }
    ctx.globalAlpha = 1
    if (sel) { const X = sel.x * k + tx, Y = sel.y * k + ty; ctx.drawImage(selS, X - h, Y - h, s, s) }
  }
  $effect(() => { shown; sel; W; H; redraw() })

  // nearest incident within a few pixels of the pointer
  function pick(e) {
    const r = svg.getBoundingClientRect(), mx = e.clientX - r.left, my = e.clientY - r.top
    const { k, x: tx, y: ty } = tr, lim = Math.max(8, 4 * Math.pow(k, .3)) ** 2
    let best = null, bd = lim
    for (const d of shown) { const dx = d.x * k + tx - mx, dy = d.y * k + ty - my, q = dx * dx + dy * dy; if (q < bd) { bd = q; best = d } }
    return best
  }
  function open(d) {
    sel = d; summary = ''
    if (d) fetch(`/summaries/${d.s}.json`).then(r => r.json()).then(m => { if (sel?.id === d.id) summary = m[d.id] ?? '' }).catch(() => {})
  }

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
    const path = geoPath(p)
    const countries = feature(topo, topo.objects.countries)
    countries.features = countries.features.filter(f => f.id !== '010')
    land = path(countries); borders = path(mesh(topo, topo.objects.countries, (a, b) => a !== b))
    sphere = path({ type: 'Sphere' }); grat = path(geoGraticule10())
    incidents = place(raw, p); sel = null
    const [[bx0, by0], [bx1, by1]] = path.bounds(frame)
    zoomer = d3zoom().scaleExtent([1, 20]).translateExtent([[Math.min(0, bx0), Math.min(0, by0)], [Math.max(cw, bx1), Math.max(ch, by1)]])
      .on('zoom', e => { tr = e.transform; select(svg).select('g.zoom').attr('transform', tr); redraw() })
    select(svg).call(zoomer).on('dblclick.zoom', null)
    // portrait: start centred on Europe/Africa
    const t = portrait ? zoomIdentity.translate(cw / 2 - p([12, 30])[0], 0) : zoomIdentity
    select(svg).call(zoomer.transform, t)
  }

  onMount(() => {
    sprites()
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
    <p>{shown.length.toLocaleString('en-GB')} of {incidents.length.toLocaleString('en-GB')} incidents · <span class="legend">fewer <span class="ramp"></span> more incidents</span> · <span class="key dot"></span> place / HQ <span class="key ring"></span> country only</p>
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
    <svg bind:this={svg} viewBox="0 0 {W} {H}" width={W} height={H} role="img" aria-label="World map of AI incidents. Click a red point for details." class:hover
         onclick={(e) => open(pick(e))} onpointermove={(e) => hover = e.pointerType === 'mouse' && !!pick(e)}>
      <g class="zoom">
        <path class="sphere" d={sphere} />
        <path class="grat" d={grat} />
        <path class="land" d={land} />
        <path class="borders" d={borders} />
      </g>
    </svg>
    <canvas bind:this={cv} style="width:{W}px;height:{H}px" aria-hidden="true"></canvas>
  </div>
  {#if sel}
    <aside class="pop" aria-live="polite">
      <button class="x" aria-label="Close" onclick={() => sel = null}>×</button>
      <div class="meta">{#if sel.kind === 'research'}<span class="rk">RESEARCH / POLICY</span> · {/if}{fmt(sel.date)} · <span class="tag">{short(sel.category)}</span> · <span class="st">{sel.status}</span></div>
      <h2>{sel.title}</h2>
      <p class="sum">{summary || '…'}</p>
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
  .sphere,.grat,.borders{vector-effect:non-scaling-stroke}
  .sphere{fill:rgba(1,10,4,.75);stroke:var(--gd);stroke-width:.6}
  .grat{fill:none;stroke:#0c3a19;stroke-width:.4}
  .land{fill:#06240f;stroke:none}
  .borders{fill:none;stroke:#1d6b35;stroke-width:.6}
  svg.hover{cursor:pointer}
  canvas{position:absolute;left:0;top:0;pointer-events:none}
  .legend{white-space:nowrap}.ramp{display:inline-block;width:70px;height:8px;vertical-align:middle;margin:0 4px;border-radius:4px;background:linear-gradient(90deg,#1a0404,#4a0c0c,#8c1a1a,#d0403a,#ff8a78)}
  .pop{position:absolute;right:16px;top:110px;width:min(380px,calc(100% - 32px));max-height:calc(100% - 160px);overflow:auto;background:rgba(1,12,5,.95);border:1px solid var(--g);box-shadow:0 0 18px rgba(57,255,106,.35);padding:14px 16px;border-radius:4px;font-size:13px;line-height:1.45}
  .pop h2{font-size:15px;margin:6px 0;color:#eafff0}
  .meta{font-size:11px;color:#8be3a3}.tag{color:var(--g)}.st{border:1px solid var(--gd);padding:0 4px}
  .sum{color:#bfe9cb;margin:6px 0 8px}.loc{font-size:11px;color:#8be3a3;margin-bottom:6px}
  .x{position:absolute;right:6px;top:4px;background:none;border:0;color:var(--g);font-size:20px;cursor:pointer}
  .key{display:inline-block;width:8px;height:8px;border-radius:50%;margin:0 2px 0 6px;vertical-align:middle}.key.dot{background:#f04a40;box-shadow:0 0 6px #f04a40}.key.ring{border:1px dashed #ff6b6b}
  .toggle{display:inline-flex;align-items:center;gap:8px;font-size:13px;color:#c9ffd6;cursor:pointer;align-self:flex-start;border:1px solid var(--gd);padding:5px 10px;border-radius:3px;background:rgba(2,12,5,.85)}
  .toggle.on{border-color:var(--g);box-shadow:0 0 8px rgba(57,255,106,.5)}
  .toggle input{position:absolute;opacity:0;width:1px;height:1px}.toggle:focus-within{outline:1px solid #fff}
  .sw{width:30px;height:16px;border-radius:8px;background:#0c3a19;position:relative;flex:none}.sw::after{content:'';position:absolute;left:2px;top:2px;width:12px;height:12px;border-radius:50%;background:#5fd47e;transition:left .15s}
  .toggle.on .sw{background:var(--g)}.toggle.on .sw::after{left:16px;background:#021}
  .toggle small{color:#7fd99a}.rk{color:#ffd76a}
  footer{font-size:11px;color:#7fd99a}
  @media (max-width:640px){.pop{top:auto;bottom:34px;right:8px;left:8px;width:auto;max-height:48%}main{padding:10px}}
</style>
