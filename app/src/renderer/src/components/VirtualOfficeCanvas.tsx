import { useEffect, useRef, useState, useCallback } from 'react'

// ── Constants ──────────────────────────────────────────
const TILE = 32
const HALF = TILE / 2
const COLS = 30
const ROWS = 20
const W = COLS * TILE
const H = ROWS * TILE
const AGENT_R = 10
const WALK_SPEED = 1.5

// ── Types ──────────────────────────────────────────────

type AgentState = 'idle' | 'working' | 'meeting' | 'walking'

interface AgentPos {
  x: number
  y: number
}

interface AgentDef {
  id: string
  name: string
  role: string
  dept: string
  color: string
  initials: string
  state: AgentState
  task: string
}

interface AgentRuntime extends AgentDef {
  x: number
  y: number
  targetX: number
  targetY: number
  deskX: number
  deskY: number
  faceDir: number
  tick: number
  path: AgentPos[]
  pathIdx: number
  stateLabel: string
  isWalking: boolean
}

// ── Department layout ──────────────────────────────────

const DEPT_ZONES: Record<string, { x: number; y: number; w: number; h: number; label: string; color: string }> = {
  Leadership: { x: 10, y: 2, w: 8, h: 4, label: 'Leadership', color: 'rgba(61,220,151,0.08)' },
  Product:    { x: 2,  y: 8, w: 7, h: 6, label: 'Product', color: 'rgba(245,158,11,0.08)' },
  Engineering:{ x: 18, y: 8, w: 8, h: 6, label: 'Engineering', color: 'rgba(34,211,238,0.08)' },
  Platform:   { x: 10, y: 15, w: 8, h: 4, label: 'Platform', color: 'rgba(167,139,250,0.08)' },
}

// Meeting room
const MEETING = { x: 27, y: 7, w: 3, h: 6, label: 'Meeting Room', color: 'rgba(52,211,153,0.06)' }

// ── Agent definitions (15 workers) ─────────────────────

const DEFAULT_AGENTS: AgentDef[] = [
  { id: 'hermes',    name: 'Hermes',  role: 'Dispatcher',   dept: 'Leadership',  color: '#3ddc97', initials: 'HE', state: 'idle', task: '' },
  { id: 'rex',       name: 'Rex',     role: 'Governor',     dept: 'Leadership',  color: '#3ddc97', initials: 'RX', state: 'idle', task: '' },
  { id: 'aria',      name: 'Aria',    role: 'PM',           dept: 'Product',     color: '#f59e0b', initials: 'AR', state: 'idle', task: '' },
  { id: 'sage',      name: 'Sage',    role: 'Research',     dept: 'Product',     color: '#f59e0b', initials: 'SG', state: 'idle', task: '' },
  { id: 'luna',      name: 'Luna',    role: 'Designer',     dept: 'Product',     color: '#f59e0b', initials: 'LN', state: 'idle', task: '' },
  { id: 'echo',      name: 'Echo',    role: 'Docs',         dept: 'Product',     color: '#f59e0b', initials: 'EC', state: 'idle', task: '' },
  { id: 'atlas',     name: 'Atlas',   role: 'Architect',    dept: 'Engineering', color: '#22d3ee', initials: 'AT', state: 'idle', task: '' },
  { id: 'hugo',      name: 'Hugo',    role: 'Backend',      dept: 'Engineering', color: '#22d3ee', initials: 'HG', state: 'idle', task: '' },
  { id: 'leo',       name: 'Leo',     role: 'Frontend',     dept: 'Engineering', color: '#22d3ee', initials: 'LE', state: 'idle', task: '' },
  { id: 'eve',       name: 'Eve',     role: 'QA',           dept: 'Engineering', color: '#22d3ee', initials: 'EV', state: 'idle', task: '' },
  { id: 'pulse',     name: 'Pulse',   role: 'Perf',         dept: 'Engineering', color: '#22d3ee', initials: 'PL', state: 'idle', task: '' },
  { id: 'nova',      name: 'Nova',    role: 'Database',     dept: 'Platform',    color: '#a78bfa', initials: 'NV', state: 'idle', task: '' },
  { id: 'nexus',     name: 'Nexus',   role: 'Integration',  dept: 'Platform',    color: '#a78bfa', initials: 'NX', state: 'idle', task: '' },
  { id: 'flint',     name: 'Flint',   role: 'Infra',        dept: 'Platform',    color: '#a78bfa', initials: 'FL', state: 'idle', task: '' },
  { id: 'sentinel',  name: 'Sentinel',role: 'Security',     dept: 'Platform',    color: '#a78bfa', initials: 'SE', state: 'idle', task: '' },
]

// ── Desk positions per department ──────────────────────

function getDeskPositions(): Record<string, AgentPos> {
  const desks: Record<string, AgentPos> = {}
  // Leadership — top center
  desks['hermes'] = { x: 12 * TILE + HALF, y: 3 * TILE + HALF }
  desks['rex']    = { x: 15 * TILE + HALF, y: 3 * TILE + HALF }
  // Product — left wing
  desks['aria']  = { x: 3 * TILE + HALF, y: 9 * TILE + HALF }
  desks['sage']  = { x: 6 * TILE + HALF, y: 9 * TILE + HALF }
  desks['luna']  = { x: 3 * TILE + HALF, y: 11 * TILE + HALF }
  desks['echo']  = { x: 6 * TILE + HALF, y: 11 * TILE + HALF }
  // Engineering — right wing
  desks['atlas'] = { x: 19 * TILE + HALF, y: 9 * TILE + HALF }
  desks['hugo']  = { x: 22 * TILE + HALF, y: 9 * TILE + HALF }
  desks['leo']   = { x: 24 * TILE + HALF, y: 9 * TILE + HALF }
  desks['eve']   = { x: 19 * TILE + HALF, y: 11 * TILE + HALF }
  desks['pulse'] = { x: 22 * TILE + HALF, y: 11 * TILE + HALF }
  // Platform — bottom center
  desks['nova']     = { x: 11 * TILE + HALF, y: 16 * TILE + HALF }
  desks['nexus']    = { x: 14 * TILE + HALF, y: 16 * TILE + HALF }
  desks['flint']    = { x: 17 * TILE + HALF, y: 16 * TILE + HALF }
  desks['sentinel'] = { x: 14 * TILE + HALF, y: 18 * TILE + HALF }
  return desks
}

// ── Meeting slots ──────────────────────────────────────

function getMeetingSlots(): AgentPos[] {
  const slots: AgentPos[] = []
  const baseX = MEETING.x * TILE + HALF
  const baseY = MEETING.y * TILE + HALF
  for (let r = 0; r < 2; r++) {
    for (let c = 0; c < 3; c++) {
      slots.push({ x: baseX + c * 40, y: baseY + r * 35 })
    }
  }
  return slots
}

// ── A* Pathfinding ─────────────────────────────────────

function findPath(sx: number, sy: number, ex: number, ey: number): AgentPos[] {
  const scx = Math.floor(sx / TILE), scy = Math.floor(sy / TILE)
  const ecx = Math.floor(ex / TILE), ecy = Math.floor(ey / TILE)
  if (scx === ecx && scy === ecy) return []

  const key = (x: number, y: number) => y * COLS + x
  const open: { x: number; y: number; g: number; h: number; f: number; p: number | null }[] = []
  const closed = new Set<number>()
  const dirs = [[0, -1], [1, 0], [0, 1], [-1, 0]]

  const start = { x: scx, y: scy, g: 0, h: Math.abs(ecx - scx) + Math.abs(ecy - scy), f: 0, p: null as number | null }
  start.f = start.h
  open.push(start)

  let iterations = 0
  while (open.length > 0 && iterations < 2000) {
    iterations++
    let best = 0
    for (let i = 1; i < open.length; i++) if (open[i].f < open[best].f) best = i
    const cur = open.splice(best, 1)[0]
    const ck = key(cur.x, cur.y)
    if (closed.has(ck)) continue
    closed.add(ck)

    if (cur.x === ecx && cur.y === ecy) {
      const path: AgentPos[] = []
      let node: typeof cur | null = cur
      while (node) { path.unshift({ x: node.x * TILE + HALF, y: node.y * TILE + HALF }); node = node.p !== null ? open.find(n => key(n.x, n.y) === node!.p) || null : null }
      path.shift()
      return path
    }

    for (const [dx, dy] of dirs) {
      const nx = cur.x + dx, ny = cur.y + dy
      if (nx < 0 || nx >= COLS || ny < 0 || ny >= ROWS) continue
      const nk = key(nx, ny)
      if (closed.has(nk)) continue
      const g = cur.g + 1
      const h = Math.abs(ecx - nx) + Math.abs(ecy - ny)
      open.push({ x: nx, y: ny, g, h, f: g + h, p: ck })
    }
  }
  return [{ x: ex, y: ey }]
}

// ── Canvas drawing helpers ─────────────────────────────

function drawGrid(ctx: CanvasRenderingContext2D) {
  ctx.strokeStyle = 'rgba(255,255,255,0.03)'
  ctx.lineWidth = 1
  for (let x = 0; x <= W; x += TILE) { ctx.beginPath(); ctx.moveTo(x, 0); ctx.lineTo(x, H); ctx.stroke() }
  for (let y = 0; y <= H; y += TILE) { ctx.beginPath(); ctx.moveTo(0, y); ctx.lineTo(W, y); ctx.stroke() }
}

function drawDeptZone(ctx: CanvasRenderingContext2D, zone: typeof DEPT_ZONES[string]) {
  const x = zone.x * TILE, y = zone.y * TILE, w = zone.w * TILE, h = zone.h * TILE
  ctx.fillStyle = zone.color
  ctx.strokeStyle = 'rgba(255,255,255,0.06)'
  ctx.lineWidth = 1
  ctx.beginPath()
  ctx.roundRect(x, y, w, h, 8)
  ctx.fill()
  ctx.stroke()
  ctx.fillStyle = 'rgba(255,255,255,0.25)'
  ctx.font = '10px Inter, system-ui, sans-serif'
  ctx.textAlign = 'center'
  ctx.fillText(zone.label, x + w / 2, y + 14)
}

function drawMeetingRoom(ctx: CanvasRenderingContext2D) {
  const x = MEETING.x * TILE, y = MEETING.y * TILE, w = MEETING.w * TILE, h = MEETING.h * TILE
  ctx.fillStyle = MEETING.color
  ctx.strokeStyle = 'rgba(52,211,153,0.2)'
  ctx.lineWidth = 1.5
  ctx.setLineDash([4, 4])
  ctx.beginPath()
  ctx.roundRect(x, y, w, h, 8)
  ctx.fill()
  ctx.stroke()
  ctx.setLineDash([])

  // Table
  ctx.fillStyle = 'rgba(52,211,153,0.12)'
  ctx.beginPath()
  ctx.roundRect(x + 15, y + 25, w - 30, h - 50, 4)
  ctx.fill()
  ctx.strokeStyle = 'rgba(52,211,153,0.25)'
  ctx.strokeRect(x + 15, y + 25, w - 30, h - 50)

  ctx.fillStyle = 'rgba(52,211,153,0.5)'
  ctx.font = '10px Inter, system-ui, sans-serif'
  ctx.textAlign = 'center'
  ctx.fillText('Meeting Room', x + w / 2, y + 14)
}

function drawDesk(ctx: CanvasRenderingContext2D, x: number, y: number, occupied: boolean) {
  // Desk surface
  ctx.fillStyle = occupied ? 'rgba(255,255,255,0.06)' : 'rgba(255,255,255,0.03)'
  ctx.strokeStyle = 'rgba(255,255,255,0.1)'
  ctx.lineWidth = 1
  ctx.beginPath()
  ctx.roundRect(x - 14, y - 10, 28, 20, 3)
  ctx.fill()
  ctx.stroke()
  // Monitor
  ctx.fillStyle = occupied ? 'rgba(52,211,153,0.15)' : 'rgba(255,255,255,0.04)'
  ctx.fillRect(x - 8, y - 8, 16, 10)
  if (occupied) {
    // Screen glow
    ctx.fillStyle = 'rgba(52,211,153,0.08)'
    ctx.fillRect(x - 6, y - 6, 12, 6)
  }
  // Stand
  ctx.fillStyle = 'rgba(255,255,255,0.08)'
  ctx.fillRect(x - 3, y + 2, 6, 3)
}

function drawAgent(ctx: CanvasRenderingContext2D, agent: AgentRuntime, now: number) {
  const { x, y, color, initials, state, name, role, isWalking } = agent

  // Shadow
  ctx.fillStyle = 'rgba(0,0,0,0.3)'
  ctx.beginPath()
  ctx.ellipse(x, y + AGENT_R + 2, AGENT_R * 0.8, 3, 0, 0, Math.PI * 2)
  ctx.fill()

  // Body
  const glow = state === 'working' || state === 'meeting'
  if (glow) {
    ctx.shadowColor = color
    ctx.shadowBlur = 8
  }
  ctx.fillStyle = color
  ctx.beginPath()
  ctx.arc(x, y, AGENT_R, 0, Math.PI * 2)
  ctx.fill()
  ctx.shadowBlur = 0

  // Initials
  ctx.fillStyle = '#000'
  ctx.font = 'bold 9px Inter, system-ui, sans-serif'
  ctx.textAlign = 'center'
  ctx.textBaseline = 'middle'
  ctx.fillText(initials, x, y + 1)

  // Walking animation — bobbing
  if (isWalking) {
    const bob = Math.sin(now / 120) * 2
    ctx.fillStyle = color
    ctx.beginPath()
    ctx.arc(x, y - AGENT_R - 4 + bob, 3, 0, Math.PI * 2)
    ctx.fill()
  }

  // State indicator dot
  const dotColors: Record<AgentState, string> = {
    idle: '#f59e0b',
    working: '#3ddc97',
    meeting: '#22d3ee',
    walking: '#a78bfa',
  }
  ctx.fillStyle = dotColors[state] || '#666'
  ctx.beginPath()
  ctx.arc(x + AGENT_R - 2, y - AGENT_R + 2, 3, 0, Math.PI * 2)
  ctx.fill()

  // Name label
  ctx.fillStyle = 'rgba(255,255,255,0.8)'
  ctx.font = '9px Inter, system-ui, sans-serif'
  ctx.textAlign = 'center'
  ctx.textBaseline = 'top'
  ctx.fillText(name, x, y + AGENT_R + 4)

  // Status label
  if (agent.stateLabel) {
    ctx.fillStyle = 'rgba(255,255,255,0.4)'
    ctx.font = '8px Inter, system-ui, sans-serif'
    ctx.fillText(agent.stateLabel, x, y + AGENT_R + 14)
  }

  // Typing animation for working state
  if (state === 'working') {
    const dotOffset = Math.floor(now / 300) % 3
    for (let i = 0; i < 3; i++) {
      ctx.fillStyle = i <= dotOffset ? 'rgba(52,211,153,0.8)' : 'rgba(52,211,153,0.2)'
      ctx.beginPath()
      ctx.arc(x - 4 + i * 4, y - AGENT_R - 8, 1.5, 0, Math.PI * 2)
      ctx.fill()
    }
  }

  // Meeting icon
  if (state === 'meeting') {
    ctx.fillStyle = 'rgba(34,211,238,0.8)'
    ctx.font = '10px Inter, system-ui, sans-serif'
    ctx.fillText('💬', x, y - AGENT_R - 12)
  }
}

// ── Main Component ─────────────────────────────────────

interface VirtualOfficeProps {
  workers?: { id: string; state: string; task?: string }[]
  onWorkerClick?: (id: string) => void
}

export function VirtualOfficeCanvas({ workers = [], onWorkerClick }: VirtualOfficeProps) {
  const canvasRef = useRef<HTMLCanvasElement>(null)
  const animRef = useRef<number>(0)
  const agentsRef = useRef<AgentRuntime[]>([])
  const desksRef = useRef(getDeskPositions())
  const meetingSlotsRef = useRef(getMeetingSlots())
  const [hoveredAgent, setHoveredAgent] = useState<string | null>(null)

  // Initialize agents
  useEffect(() => {
    const desks = desksRef.current
    agentsRef.current = DEFAULT_AGENTS.map(def => {
      const desk = desks[def.id] || { x: 100, y: 100 }
      return {
        ...def,
        x: desk.x,
        y: desk.y,
        targetX: desk.x,
        targetY: desk.y,
        deskX: desk.x,
        deskY: desk.y,
        faceDir: 1,
        tick: Math.floor(Math.random() * 1000),
        path: [],
        pathIdx: 0,
        stateLabel: '',
        isWalking: false,
      }
    })
  }, [])

  // Update agent states from backend
  useEffect(() => {
    const agents = agentsRef.current
    const slots = meetingSlotsRef.current
    let slotI = 0

    for (const w of workers) {
      const agent = agents.find(a => a.id === w.id)
      if (!agent) continue

      const newState = (w.state || 'idle') as AgentState
      const task = w.task || ''

      if (agent.state !== newState || agent.task !== task) {
        agent.state = newState
        agent.task = task

        // Determine target
        if (newState === 'meeting') {
          const slot = slots[slotI % slots.length]
          slotI++
          agent.targetX = slot.x
          agent.targetY = slot.y
          agent.stateLabel = 'In meeting'
          agent.path = findPath(agent.x, agent.y, agent.targetX, agent.targetY)
          agent.pathIdx = 0
        } else if (newState === 'working') {
          agent.targetX = agent.deskX
          agent.targetY = agent.deskY
          agent.stateLabel = task || 'Working'
          agent.path = findPath(agent.x, agent.y, agent.targetX, agent.targetY)
          agent.pathIdx = 0
        } else {
          agent.targetX = agent.deskX
          agent.targetY = agent.deskY
          agent.stateLabel = ''
          agent.path = findPath(agent.x, agent.y, agent.targetX, agent.targetY)
          agent.pathIdx = 0
        }
      }
    }
  }, [workers])

  // Animation loop
  useEffect(() => {
    const canvas = canvasRef.current
    if (!canvas) return
    const ctx = canvas.getContext('2d')
    if (!ctx) return

    const dpr = window.devicePixelRatio || 1
    canvas.width = W * dpr
    canvas.height = H * dpr
    canvas.style.width = `${W}px`
    canvas.style.height = `${H}px`
    ctx.scale(dpr, dpr)

    const render = (now: number) => {
      // Background
      ctx.fillStyle = '#0a0e14'
      ctx.fillRect(0, 0, W, H)

      // Grid
      drawGrid(ctx)

      // Department zones
      for (const zone of Object.values(DEPT_ZONES)) {
        drawDeptZone(ctx, zone)
      }

      // Meeting room
      drawMeetingRoom(ctx)

      // Desks
      const desks = desksRef.current
      for (const [id, pos] of Object.entries(desks)) {
        const agent = agentsRef.current.find(a => a.id === id)
        drawDesk(ctx, pos.x, pos.y, !!agent && agent.state !== 'meeting')
      }

      // Update and draw agents
      for (const agent of agentsRef.current) {
        // Movement along path
        if (agent.path.length > 0 && agent.pathIdx < agent.path.length) {
          const target = agent.path[agent.pathIdx]
          const dx = target.x - agent.x
          const dy = target.y - agent.y
          const dist = Math.sqrt(dx * dx + dy * dy)

          if (dist < WALK_SPEED) {
            agent.x = target.x
            agent.y = target.y
            agent.pathIdx++
            if (agent.pathIdx >= agent.path.length) {
              agent.isWalking = false
              agent.path = []
              agent.pathIdx = 0
            }
          } else {
            agent.x += (dx / dist) * WALK_SPEED
            agent.y += (dy / dist) * WALK_SPEED
            agent.isWalking = true
            agent.faceDir = dx > 0 ? 1 : -1
          }
        }

        agent.tick++
        drawAgent(ctx, agent, now)
      }

      // Hover tooltip
      if (hoveredAgent) {
        const agent = agentsRef.current.find(a => a.id === hoveredAgent)
        if (agent) {
          ctx.fillStyle = 'rgba(13,17,23,0.95)'
          ctx.strokeStyle = 'rgba(255,255,255,0.15)'
          ctx.lineWidth = 1
          const tw = 140, th = 50
          const tx = Math.min(agent.x - tw / 2, W - tw - 10)
          const ty = Math.max(agent.y - AGENT_R - th - 10, 10)
          ctx.beginPath()
          ctx.roundRect(tx, ty, tw, th, 6)
          ctx.fill()
          ctx.stroke()
          ctx.fillStyle = '#fff'
          ctx.font = 'bold 11px Inter, system-ui, sans-serif'
          ctx.textAlign = 'left'
          ctx.textBaseline = 'top'
          ctx.fillText(`${agent.name} — ${agent.role}`, tx + 8, ty + 8)
          ctx.fillStyle = agent.color
          ctx.font = '10px Inter, system-ui, sans-serif'
          ctx.fillText(`${agent.dept} · ${agent.state}${agent.task ? ': ' + agent.task : ''}`, tx + 8, ty + 26)
        }
      }

      animRef.current = requestAnimationFrame(render)
    }

    animRef.current = requestAnimationFrame(render)
    return () => cancelAnimationFrame(animRef.current)
  }, [hoveredAgent])

  // Mouse interaction
  const handleMouseMove = useCallback((e: React.MouseEvent<HTMLCanvasElement>) => {
    const rect = canvasRef.current?.getBoundingClientRect()
    if (!rect) return
    const mx = e.clientX - rect.left
    const my = e.clientY - rect.top

    let found: string | null = null
    for (const agent of agentsRef.current) {
      const dx = mx - agent.x, dy = my - agent.y
      if (dx * dx + dy * dy < (AGENT_R + 4) * (AGENT_R + 4)) {
        found = agent.id
        break
      }
    }
    setHoveredAgent(found)
  }, [])

  const handleClick = useCallback((e: React.MouseEvent<HTMLCanvasElement>) => {
    const rect = canvasRef.current?.getBoundingClientRect()
    if (!rect) return
    const mx = e.clientX - rect.left
    const my = e.clientY - rect.top

    for (const agent of agentsRef.current) {
      const dx = mx - agent.x, dy = my - agent.y
      if (dx * dx + dy * dy < (AGENT_R + 4) * (AGENT_R + 4)) {
        onWorkerClick?.(agent.id)
        break
      }
    }
  }, [onWorkerClick])

  return (
    <div className="relative overflow-hidden rounded-xl border border-border bg-[#0a0e14]">
      <canvas
        ref={canvasRef}
        onMouseMove={handleMouseMove}
        onClick={handleClick}
        className="block cursor-default"
        style={{ width: W, height: H }}
      />
      {/* Stats overlay */}
      <div className="absolute bottom-2 right-2 flex gap-2 text-[10px] text-muted-foreground/60">
        <span className="flex items-center gap-1"><span className="size-1.5 rounded-full bg-success" /> Working</span>
        <span className="flex items-center gap-1"><span className="size-1.5 rounded-full bg-warning" /> Idle</span>
        <span className="flex items-center gap-1"><span className="size-1.5 rounded-full bg-info" /> Meeting</span>
      </div>
    </div>
  )
}
