<script>
  import { onMount } from 'svelte'
  let c
  onMount(() => {
    const ctx = c.getContext('2d'); const fs = 16; let cols, drops, raf, last = 0
    const reduce = matchMedia('(prefers-reduced-motion: reduce)').matches
    const size = () => { c.width = innerWidth; c.height = innerHeight; cols = Math.ceil(c.width / fs); drops = Array.from({ length: cols }, () => Math.random() * -c.height / fs) }
    size(); addEventListener('resize', size)
    const draw = (t) => {
      raf = requestAnimationFrame(draw); if (t - last < 55) return; last = t
      ctx.fillStyle = 'rgba(2,7,3,0.12)'; ctx.fillRect(0, 0, c.width, c.height)
      ctx.font = fs + 'px monospace'
      for (let i = 0; i < cols; i++) {
        const y = drops[i] * fs
        ctx.fillStyle = Math.random() > 0.96 ? '#b8ffc8' : '#1fa846'
        ctx.fillText(Math.random() > 0.5 ? '1' : '0', i * fs, y)
        if (y > c.height && Math.random() > 0.975) drops[i] = 0
        drops[i] += 1
      }
    }
    if (reduce) { size(); ctx.fillStyle='#0b3016'; ctx.font=fs+'px monospace'; for(let i=0;i<cols;i++)for(let j=0;j<c.height/fs;j++)if(Math.random()>.7)ctx.fillText(Math.random()>.5?'1':'0',i*fs,j*fs) } else raf = requestAnimationFrame(draw)
    return () => { cancelAnimationFrame(raf); removeEventListener('resize', size) }
  })
</script>
<canvas bind:this={c} aria-hidden="true"></canvas>
<style>canvas{position:fixed;inset:0;opacity:.35;pointer-events:none;z-index:0}</style>
