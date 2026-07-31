import { useEffect, useRef, useState } from 'react'

const TILE = 28
const COLS = 32
const ROWS = 20
const W = COLS * TILE
const H = ROWS * TILE
const SPEED = 0.8

type AgentState = 'idle' | 'working' | 'meeting' | 'walking'
interface Pos { x: number; y: number }
interface AgentDef { id: string; name: string; role: string; dept: string; color: string; skin: string; hair: string; state: AgentState; task: string }
interface Agent extends AgentDef { x: number; y: number; deskX: number; deskY: number; targetX: number; targetY: number; path: Pos[]; pathIdx: number; isWalking: boolean; faceDir: number; tick: number }

const WORKERS: AgentDef[] = [
  { id: 'hermes', name: 'Hermes', role: 'Dispatcher', dept: 'Leadership', color: '#3ddc97', skin: '#f5d0a9', hair: '#333', state: 'idle', task: '' },
  { id: 'rex', name: 'Rex', role: 'Governor', dept: 'Leadership', color: '#3ddc97', skin: '#d4a574', hair: '#1a1a1a', state: 'idle', task: '' },
  { id: 'aria', name: 'Aria', role: 'PM', dept: 'Product', color: '#f59e0b', skin: '#f5d0a9', hair: '#5d4037', state: 'idle', task: '' },
  { id: 'sage', name: 'Sage', role: 'Research', dept: 'Product', color: '#f59e0b', skin: '#d4a574', hair: '#333', state: 'idle', task: '' },
  { id: 'luna', name: 'Luna', role: 'Designer', dept: 'Product', color: '#f59e0b', skin: '#f0c0a0', hair: '#bf360c', state: 'idle', task: '' },
  { id: 'echo', name: 'Echo', role: 'Docs', dept: 'Product', color: '#f59e0b', skin: '#f5d0a9', hair: '#616161', state: 'idle', task: '' },
  { id: 'atlas', name: 'Atlas', role: 'Architect', dept: 'Engineering', color: '#22d3ee', skin: '#d4a574', hair: '#263238', state: 'idle', task: '' },
  { id: 'hugo', name: 'Hugo', role: 'Backend', dept: 'Engineering', color: '#22d3ee', skin: '#f5d0a9', hair: '#1a1a1a', state: 'idle', task: '' },
  { id: 'leo', name: 'Leo', role: 'Frontend', dept: 'Engineering', color: '#22d3ee', skin: '#e8b88a', hair: '#ffd700', state: 'idle', task: '' },
  { id: 'eve', name: 'Eve', role: 'QA', dept: 'Engineering', color: '#22d3ee', skin: '#f0c0a0', hair: '#333', state: 'idle', task: '' },
  { id: 'pulse', name: 'Pulse', role: 'Perf', dept: 'Engineering', color: '#22d3ee', skin: '#d4a574', hair: '#5d4037', state: 'idle', task: '' },
  { id: 'nova', name: 'Nova', role: 'Database', dept: 'Platform', color: '#a78bfa', skin: '#f5d0a9', hair: '#1a1a1a', state: 'idle', task: '' },
  { id: 'nexus', name: 'Nexus', role: 'Integration', dept: 'Platform', color: '#a78bfa', skin: '#d4a574', hair: '#333', state: 'idle', task: '' },
  { id: 'flint', name: 'Flint', role: 'Infra', dept: 'Platform', color: '#a78bfa', skin: '#e8b88a', hair: '#bf360c', state: 'idle', task: '' },
  { id: 'sentinel', name: 'Sentinel', role: 'Security', dept: 'Platform', color: '#a78bfa', skin: '#f5d0a9', hair: '#263238', state: 'idle', task: '' },
]

const DESKS: Record<string, Pos> = {
  // Leadership — above meeting
  hermes: { x: 14, y: 3 }, rex: { x: 18, y: 3 },
  // Product — left of meeting
  aria: { x: 3, y: 8 }, sage: { x: 6, y: 8 },
  luna: { x: 3, y: 11 }, echo: { x: 6, y: 11 },
  // Engineering — right of meeting
  atlas: { x: 25, y: 8 }, hugo: { x: 28, y: 8 },
  leo: { x: 30, y: 8 }, eve: { x: 25, y: 11 },
  pulse: { x: 28, y: 11 },
  // Platform — below meeting
  nova: { x: 14, y: 16 }, nexus: { x: 17, y: 16 },
  flint: { x: 20, y: 16 }, sentinel: { x: 17, y: 18 },
}

const ZONES = [
  { x: 12, y: 1, w: 8, h: 4, label: 'Leadership',  border: 'rgba(61,220,151,0.12)' },
  { x: 1,  y: 6, w: 8, h: 7, label: 'Product',     border: 'rgba(245,158,11,0.12)' },
  { x: 23, y: 6, w: 8, h: 7, label: 'Engineering', border: 'rgba(34,211,238,0.12)' },
  { x: 12, y: 14, w: 10, h: 5, label: 'Platform',    border: 'rgba(167,139,250,0.12)' },
]

const MEETING_CENTER = { x: 16, y: 10 }
const MEETING_SLOTS: Pos[] = [
  { x: 13, y: 8 }, { x: 16, y: 7 }, { x: 19, y: 8 },
  { x: 13, y: 12 }, { x: 16, y: 13 }, { x: 19, y: 12 },
  { x: 12, y: 10 }, { x: 20, y: 10 },
]

// ── A* ──
function findPath(sx: number, sy: number, ex: number, ey: number): Pos[] {
  const s = { x: Math.floor(sx), y: Math.floor(sy) }, e = { x: Math.floor(ex), y: Math.floor(ey) }
  if (s.x === e.x && s.y === e.y) return []
  const key = (x: number, y: number) => y * COLS + x
  const open: { x: number; y: number; g: number; h: number; f: number; p: number | null }[] = []
  const closed = new Set<number>()
  const start = { x: s.x, y: s.y, g: 0, h: Math.abs(e.x - s.x) + Math.abs(e.y - s.y), f: 0, p: null as number | null }
  start.f = start.h; open.push(start)
  let iter = 0
  while (open.length > 0 && iter < 1000) {
    iter++; let best = 0
    for (let i = 1; i < open.length; i++) if (open[i].f < open[best].f) best = i
    const cur = open.splice(best, 1)[0], ck = key(cur.x, cur.y)
    if (closed.has(ck)) continue; closed.add(ck)
    if (cur.x === e.x && cur.y === e.y) {
      const path: Pos[] = []; let n: typeof cur | null = cur
      while (n) { path.unshift({ x: n.x, y: n.y }); n = n.p !== null ? open.find(o => key(o.x, o.y) === n!.p) || null : null }
      path.shift(); return path
    }
    for (const [dx, dy] of [[0,-1],[1,0],[0,1],[-1,0]]) {
      const nx = cur.x + dx, ny = cur.y + dy
      if (nx < 0 || nx >= COLS || ny < 0 || ny >= ROWS) continue
      const nk = key(nx, ny); if (closed.has(nk)) continue
      open.push({ x: nx, y: ny, g: cur.g + 1, h: Math.abs(e.x - nx) + Math.abs(e.y - ny), f: cur.g + 1 + Math.abs(e.x - nx) + Math.abs(e.y - ny), p: ck })
    }
  }
  return [{ x: ex, y: ey }]
}

// ── Pixel Art Drawing ──

function drawFloor(ctx: CanvasRenderingContext2D) {
  ctx.fillStyle = '#0a0e14'; ctx.fillRect(0, 0, W, H)
  ctx.strokeStyle = 'rgba(255,255,255,0.02)'; ctx.lineWidth = 1
  for (let x = 0; x <= W; x += TILE) { ctx.beginPath(); ctx.moveTo(x, 0); ctx.lineTo(x, H); ctx.stroke() }
  for (let y = 0; y <= H; y += TILE) { ctx.beginPath(); ctx.moveTo(0, y); ctx.lineTo(W, y); ctx.stroke() }
}

function drawZone(ctx: CanvasRenderingContext2D, z: typeof ZONES[0]) {
  ctx.fillStyle = 'rgba(255,255,255,0.02)'; ctx.strokeStyle = z.border; ctx.lineWidth = 1
  ctx.beginPath(); ctx.roundRect(z.x * TILE, z.y * TILE, z.w * TILE, z.h * TILE, 6); ctx.fill(); ctx.stroke()
  ctx.fillStyle = 'rgba(255,255,255,0.12)'; ctx.font = 'bold 8px Inter,system-ui,sans-serif'; ctx.textAlign = 'center'
  ctx.fillText(z.label, (z.x + z.w / 2) * TILE, z.y * TILE + 10)
}

function drawDesk(ctx: CanvasRenderingContext2D, x: number, y: number, color: string, active: boolean) {
  const dx = x * TILE, dy = y * TILE
  ctx.save(); ctx.translate(dx, dy)
  // Shadow
  ctx.fillStyle = 'rgba(0,0,0,0.15)'; ctx.fillRect(-30, -18, 60, 40)
  // Desk surface
  ctx.fillStyle = '#5d4037'; ctx.fillRect(-28, -20, 56, 36)
  ctx.fillStyle = '#795548'; ctx.fillRect(-26, -18, 52, 32)
  ctx.fillStyle = '#8d6e63'; ctx.fillRect(-24, -16, 48, 28)
  // Edge
  ctx.fillStyle = '#4e342e'; ctx.fillRect(-28, 14, 56, 3)
  // Legs
  ctx.fillStyle = '#3e2723'; ctx.fillRect(-26, 16, 3, 5); ctx.fillRect(23, 16, 3, 5)
  // Monitor
  ctx.fillStyle = '#263238'; ctx.fillRect(-16, -40, 32, 20)
  ctx.fillStyle = active ? 'rgba(79,195,247,0.25)' : 'rgba(33,150,243,0.1)'; ctx.fillRect(-14, -38, 28, 16)
  // Code lines
  if (active) {
    ctx.fillStyle = 'rgba(79,195,247,0.3)'; ctx.fillRect(-12, -35, 20, 1); ctx.fillRect(-12, -32, 16, 1); ctx.fillRect(-12, -29, 22, 1)
  }
  // Stand
  ctx.fillStyle = '#37474f'; ctx.fillRect(-4, -20, 8, 3)
  // Keyboard
  ctx.fillStyle = '#455a64'; ctx.fillRect(-12, -14, 24, 6)
  ctx.fillStyle = '#546e7a'; for (let i = 0; i < 4; i++) ctx.fillRect(-10 + i * 5, -12, 3, 2)
  // Mouse
  ctx.fillStyle = '#78909c'; ctx.fillRect(16, -3, 5, 6); ctx.fillStyle = '#90a4ae'; ctx.fillRect(17, -2, 3, 2)
  ctx.restore()
}

function drawMeetingTable(ctx: CanvasRenderingContext2D) {
  const cx = MEETING_CENTER.x * TILE, cy = MEETING_CENTER.y * TILE
  ctx.save(); ctx.translate(cx, cy)
  // Table shadow
  ctx.fillStyle = 'rgba(0,0,0,0.15)'; ctx.beginPath(); ctx.ellipse(0, 2, 50, 28, 0, 0, Math.PI * 2); ctx.fill()
  // Table surface (oval/round)
  ctx.fillStyle = '#5d4037'; ctx.beginPath(); ctx.ellipse(0, 0, 48, 26, 0, 0, Math.PI * 2); ctx.fill()
  ctx.fillStyle = '#795548'; ctx.beginPath(); ctx.ellipse(0, -2, 44, 22, 0, 0, Math.PI * 2); ctx.fill()
  ctx.fillStyle = '#8d6e63'; ctx.beginPath(); ctx.ellipse(0, -3, 40, 18, 0, 0, Math.PI * 2); ctx.fill()
  // Table edge highlight
  ctx.strokeStyle = 'rgba(255,255,255,0.06)'; ctx.lineWidth = 1
  ctx.beginPath(); ctx.ellipse(0, -3, 40, 18, 0, 0, Math.PI * 2); ctx.stroke()
  ctx.restore()

  // Chairs around table
  for (const s of MEETING_SLOTS) {
    const sx = s.x * TILE, sy = s.y * TILE
    ctx.fillStyle = '#37474f'; ctx.fillRect(sx - 4, sy - 4, 8, 8)
    ctx.fillStyle = '#455a64'; ctx.fillRect(sx - 3, sy - 3, 6, 6)
  }
}

function drawCharacter(ctx: CanvasRenderingContext2D, a: Agent, now: number) {
  const x = a.x * TILE + TILE / 2, y = a.y * TILE + TILE / 2
  const moving = a.isWalking
  const bob = moving ? Math.sin(now / 80) * 1.5 : 0
  const breathe = !moving ? Math.sin(now / 600) * 0.5 : 0

  ctx.save(); ctx.translate(x, y + bob)

  // Shadow
  ctx.fillStyle = 'rgba(0,0,0,0.2)'; ctx.beginPath(); ctx.ellipse(0, 10, 7, 2.5, 0, 0, Math.PI * 2); ctx.fill()

  // Legs
  const legOff = moving ? Math.sin(now / 70) * 2.5 : 0
  ctx.fillStyle = '#1a1a2e'
  ctx.fillRect(-6, -1 + breathe + legOff, 4, 7)
  ctx.fillRect(2, -1 + breathe - legOff, 4, 7)

  // Body
  ctx.fillStyle = a.color
  ctx.fillRect(-7, -14 + breathe, 14, 13)

  // Arms
  const armColor = a.color
  if (a.state === 'working') {
    const t = Math.sin(now / 150) * 1.5
    ctx.fillStyle = armColor; ctx.fillRect(-10, -10 + t + breathe, 3, 7); ctx.fillRect(7, -10 - t + breathe, 3, 7)
  } else if (moving) {
    const sw = Math.sin(now / 70) * 3
    ctx.fillStyle = armColor; ctx.fillRect(-10, -10 + sw + breathe, 3, 7); ctx.fillRect(7, -10 - sw + breathe, 3, 7)
  } else {
    ctx.fillStyle = armColor; ctx.fillRect(-10, -10 + breathe, 3, 7); ctx.fillRect(7, -10 + breathe, 3, 7)
  }

  // Head
  ctx.fillStyle = a.skin; ctx.fillRect(-8, -28 + breathe, 16, 14)

  // Hair
  ctx.fillStyle = a.hair; ctx.fillRect(-8, -30 + breathe, 16, 5)
  ctx.fillRect(-9, -28 + breathe, 2, 4); ctx.fillRect(7, -28 + breathe, 2, 4)

  // Eyes
  const ed = a.faceDir === 1 ? 1 : -1
  ctx.fillStyle = '#fff'; ctx.fillRect(-4 + ed, -23 + breathe, 4, 3); ctx.fillRect(3 + ed, -23 + breathe, 4, 3)
  ctx.fillStyle = '#1a1a2e'; ctx.fillRect(-3 + ed, -22 + breathe, 2, 2); ctx.fillRect(4 + ed, -22 + breathe, 2, 2)

  // Working dots
  if (a.state === 'working') {
    const d = Math.floor(now / 180) % 3
    for (let i = 0; i < 3; i++) {
      ctx.fillStyle = i <= d ? 'rgba(52,211,153,0.8)' : 'rgba(52,211,153,0.2)'
      ctx.fillRect(-2 + i * 2, -33 + breathe, 1, 1)
    }
  }

  // Meeting bubble
  if (a.state === 'meeting') {
    ctx.fillStyle = 'rgba(34,211,238,0.7)'; ctx.beginPath()
    ctx.roundRect(7, -32 + breathe, 10, 7, 2); ctx.fill()
    ctx.fillStyle = '#fff'; ctx.font = '5px sans-serif'; ctx.textAlign = 'center'
    ctx.fillText('💬', 12, -27 + breathe)
  }

  // State dot
  const dc = { idle: '#f59e0b', working: '#3ddc97', meeting: '#22d3ee', walking: '#a78bfa' }[a.state]
  ctx.fillStyle = dc; ctx.fillRect(7, -14 + breathe, 3, 3)

  // Name
  ctx.fillStyle = 'rgba(255,255,255,0.55)'; ctx.font = '7px Inter,system-ui,sans-serif'; ctx.textAlign = 'center'
  ctx.fillText(a.name, 0, 15)

  ctx.restore()
}

function drawFurniture(ctx: CanvasRenderingContext2D) {
  // Coffee machine (top-left)
  ctx.fillStyle = 'rgba(139,92,42,0.12)'; ctx.fillRect(10 * TILE, 2 * TILE, 12, 16)
  ctx.fillStyle = 'rgba(255,255,255,0.05)'; ctx.fillRect(10 * TILE + 2, 2 * TILE + 2, 8, 5)
  // Water cooler (top-right)
  ctx.fillStyle = 'rgba(33,150,243,0.08)'; ctx.fillRect(21 * TILE, 2 * TILE, 8, 14)
  ctx.fillStyle = 'rgba(33,150,243,0.15)'; ctx.fillRect(21 * TILE + 1, 2 * TILE + 2, 6, 6)
  // Plants at corners
  const plants: [number, number][] = [[1, 1], [30, 1], [1, 18], [30, 18]]
  for (const [px, py] of plants) {
    ctx.fillStyle = 'rgba(52,211,153,0.1)'; ctx.beginPath(); ctx.arc(px * TILE + 5, py * TILE, 4, 0, Math.PI * 2); ctx.fill()
    ctx.beginPath(); ctx.arc(px * TILE + 2, py * TILE + 3, 3, 0, Math.PI * 2); ctx.fill()
    ctx.fillStyle = 'rgba(139,92,42,0.1)'; ctx.fillRect(px * TILE + 2, py * TILE + 5, 5, 4)
  }
  // Bookshelf
  ctx.fillStyle = 'rgba(139,92,42,0.08)'; ctx.fillRect(10 * TILE, 15 * TILE, 20, 12)
  ctx.fillStyle = 'rgba(255,255,255,0.04)'; ctx.fillRect(10 * TILE + 2, 15 * TILE + 2, 5, 3); ctx.fillRect(10 * TILE + 9, 15 * TILE + 2, 5, 3)
}

// ── Component ──

interface Props { 
  workers?: { id: string; state: string; task?: string }[]
  onWorkerClick?: (id: string) => void
}

export function VirtualOfficeCanvas({ workers = [], onWorkerClick }: Props) {
  const canvasRef = useRef<HTMLCanvasElement>(null)
  const containerRef = useRef<HTMLDivElement>(null)
  const agentsRef = useRef<Agent[]>([])
  const [scale, setScale] = useState(1)

  useEffect(() => {
    const c = containerRef.current; if (!c) return
    const obs = new ResizeObserver(entries => { for (const e of entries) setScale(Math.min(1, e.contentRect.width / W)) })
    obs.observe(c); return () => obs.disconnect()
  }, [])

  useEffect(() => {
    agentsRef.current = WORKERS.map(def => {
      const d = DESKS[def.id] || { x: 5, y: 5 }
      return { ...def, x: d.x, y: d.y, deskX: d.x, deskY: d.y, targetX: d.x, targetY: d.y, path: [], pathIdx: 0, isWalking: false, faceDir: 1, tick: 0 }
    })
  }, [])

  useEffect(() => {
    const agents = agentsRef.current; let si = 0
    for (const w of workers) {
      const a = agents.find(ag => ag.id === w.id); if (!a) continue
      const ns = (w.state || 'idle') as AgentState
      if (a.state !== ns || a.task !== (w.task || '')) {
        a.state = ns; a.task = w.task || ''
        if (ns === 'meeting') { const s = MEETING_SLOTS[si % MEETING_SLOTS.length]; si++; a.targetX = s.x; a.targetY = s.y }
        else { a.targetX = a.deskX; a.targetY = a.deskY }
        a.path = findPath(a.x, a.y, a.targetX, a.targetY); a.pathIdx = 0
      }
    }
  }, [workers])

  useEffect(() => {
    const canvas = canvasRef.current; if (!canvas) return
    const ctx = canvas.getContext('2d'); if (!ctx) return
    const dpr = window.devicePixelRatio || 1
    canvas.width = W * dpr; canvas.height = H * dpr; canvas.style.width = `${W}px`; canvas.style.height = `${H}px`; ctx.scale(dpr, dpr)

    const render = (now: number) => {
      drawFloor(ctx)
      for (const z of ZONES) drawZone(ctx, z)
      drawFurniture(ctx)
      drawMeetingTable(ctx)

      for (const [id, pos] of Object.entries(DESKS)) {
        const a = agentsRef.current.find(ag => ag.id === id)
        drawDesk(ctx, pos.x, pos.y, a?.color || '#666', !!a && a.state !== 'meeting')
      }

      for (const a of agentsRef.current) {
        if (a.path.length > 0 && a.pathIdx < a.path.length) {
          const t = a.path[a.pathIdx], dx = t.x - a.x, dy = t.y - a.y, dist = Math.sqrt(dx * dx + dy * dy)
          if (dist < SPEED) { a.x = t.x; a.y = t.y; a.pathIdx++; if (a.pathIdx >= a.path.length) { a.isWalking = false; a.path = []; a.pathIdx = 0 } }
          else { a.x += (dx / dist) * SPEED; a.y += (dy / dist) * SPEED; a.isWalking = true; a.faceDir = dx > 0 ? 1 : -1 }
        }
        a.tick++; drawCharacter(ctx, a, now)
      }
      requestAnimationFrame(render)
    }
    requestAnimationFrame(render)
  }, [])

  const handleClick = (e: React.MouseEvent<HTMLCanvasElement>) => {
    if (!onWorkerClick) return
    const rect = canvasRef.current?.getBoundingClientRect()
    if (!rect) return
    const mx = (e.clientX - rect.left) / scale, my = (e.clientY - rect.top) / scale
    for (const a of agentsRef.current) {
      const ax = a.x * TILE + TILE / 2, ay = a.y * TILE + TILE / 2
      if (Math.abs(mx - ax) < 12 && Math.abs(my - ay) < 16) { onWorkerClick(a.id); break }
    }
  }

  return (
    <div ref={containerRef} className="relative overflow-hidden rounded-xl border border-border bg-[#0a0e14]">
      <canvas ref={canvasRef} onClick={handleClick} className="block origin-top-left cursor-default" style={{ width: W * scale, height: H * scale }} />
      <div className="absolute bottom-2 right-2 flex gap-2 text-[9px] text-muted-foreground/40">
        <span className="flex items-center gap-1"><span className="size-1.5 rounded-full bg-success" /> Working</span>
        <span className="flex items-center gap-1"><span className="size-1.5 rounded-full bg-warning" /> Idle</span>
        <span className="flex items-center gap-1"><span className="size-1.5 rounded-full bg-info" /> Meeting</span>
      </div>
    </div>
  )
}