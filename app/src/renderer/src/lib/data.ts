// Static mock data for the AIC ADE desktop UI.

export type Status = 'online' | 'idle' | 'offline' | 'busy'

export type Department = 'Leadership' | 'Product' | 'Engineering' | 'Platform'

export type Worker = {
  id: string
  name: string
  role: string
  tier: string
  department: Department
  personality: string
  phase: string
  initial: string
  avatar: string
  status: Status
  doing: string
  cpu: number
  mem: string
  memPct: number
  tasks: number
}

export const departments: Department[] = ['Leadership', 'Product', 'Engineering', 'Platform']

export const workers: Worker[] = [
  // Leadership
  { id: 'hermes', name: 'Hermes', role: 'Dispatcher', tier: 'System Tier', department: 'Leadership', phase: 'Global', personality: 'Strict butler — routes tasks, never writes code, talks to user then delegates.', initial: 'H', avatar: '/workers/hermes.png', status: 'online', doing: 'Routing tasks', cpu: 72, mem: '236MB', memPct: 62, tasks: 8 },
  { id: 'rex', name: 'Rex', role: 'Governor', tier: 'Sprinter Tier', department: 'Leadership', phase: 'Closeout', personality: 'Compliance gate — final reviewer, never auto-commits, awaits user approval.', initial: 'R', avatar: '/workers/rex.png', status: 'busy', doing: 'Reviewing PR', cpu: 44, mem: '198MB', memPct: 48, tasks: 5 },
  // Product
  { id: 'aria', name: 'Aria', role: 'Product Manager', tier: 'Thinker Tier', department: 'Product', phase: 'Investigate', personality: 'Empathetic translator — turns vague requests into user stories and acceptance criteria.', initial: 'A', avatar: '/workers/aria.png', status: 'busy', doing: 'Writing user stories', cpu: 18, mem: '142MB', memPct: 34, tasks: 3 },
  { id: 'sage', name: 'Sage', role: 'Researcher', tier: 'Thinker Tier', department: 'Product', phase: 'Investigate', personality: 'Evidence-driven analyst — finds facts, validates assumptions, no guessing.', initial: 'S', avatar: '/workers/sage.png', status: 'online', doing: 'Reading docs', cpu: 22, mem: '410MB', memPct: 71, tasks: 12 },
  { id: 'luna', name: 'Luna', role: 'Designer', tier: 'Crafter Tier', department: 'Product', phase: 'Implementation', personality: 'User advocate — specifies layouts, interactions, visual consistency.', initial: 'L', avatar: '/workers/luna.png', status: 'idle', doing: 'Away from desk', cpu: 9, mem: '176MB', memPct: 40, tasks: 4 },
  { id: 'echo', name: 'Echo', role: 'Documentation Engineer', tier: 'Sprinter Tier', department: 'Product', phase: 'Closeout', personality: 'Thorough writer — produces structured docs, reports, and changelogs.', initial: 'E', avatar: '/workers/echo.png', status: 'busy', doing: 'Drafting changelog', cpu: 64, mem: '230MB', memPct: 58, tasks: 9 },
  // Engineering
  { id: 'atlas', name: 'Atlas', role: 'Architect', tier: 'Thinker Tier', department: 'Engineering', phase: 'Planning', personality: 'Systems thinker — designs databases, APIs, tech stack, thinks in trade-offs.', initial: 'A', avatar: '/workers/atlas.png', status: 'online', doing: 'Designing schema', cpu: 31, mem: '300MB', memPct: 55, tasks: 6 },
  { id: 'hugo', name: 'Hugo', role: 'Backend Engineer', tier: 'Crafter Tier', department: 'Engineering', phase: 'Implementation', personality: 'Reliability nerd — APIs, database logic, security and performance first.', initial: 'H', avatar: '/workers/hugo.png', status: 'online', doing: 'Writing API routes', cpu: 58, mem: '268MB', memPct: 61, tasks: 7 },
  { id: 'leo', name: 'Leo', role: 'Frontend Engineer', tier: 'Crafter Tier', department: 'Engineering', phase: 'Implementation', personality: 'UI craftsman — React, Vite, Tailwind, builds what Luna designs.', initial: 'L', avatar: '/workers/leo.png', status: 'online', doing: 'Building components', cpu: 51, mem: '212MB', memPct: 52, tasks: 8 },
  { id: 'eve', name: 'Eve', role: 'QA Engineer', tier: 'Sprinter Tier', department: 'Engineering', phase: 'Verification', personality: 'Perfectionist tester — writes tests, breaks things so users don\'t have to.', initial: 'E', avatar: '/workers/eve.png', status: 'busy', doing: 'Running test suite', cpu: 67, mem: '254MB', memPct: 60, tasks: 11 },
  { id: 'pulse', name: 'Pulse', role: 'Performance Engineer', tier: 'Sprinter Tier', department: 'Engineering', phase: 'Verification', personality: 'Bottleneck hunter — profiling, load testing, makes things fast.', initial: 'P', avatar: '/workers/pulse.png', status: 'idle', doing: 'Idle — no jobs', cpu: 12, mem: '150MB', memPct: 33, tasks: 2 },
  // Platform
  { id: 'nova', name: 'Nova', role: 'Data Engineer', tier: 'Crafter Tier', department: 'Platform', phase: 'Planning', personality: 'Data specialist — schemas, migrations, ETL pipelines, data integrity.', initial: 'N', avatar: '/workers/nova.png', status: 'online', doing: 'Running migration', cpu: 39, mem: '288MB', memPct: 57, tasks: 6 },
  { id: 'nexus', name: 'Nexus', role: 'Integration Engineer', tier: 'Crafter Tier', department: 'Platform', phase: 'Planning', personality: 'Connector — API integrations, service mesh, protocol handling.', initial: 'N', avatar: '/workers/nexus.png', status: 'online', doing: 'Wiring webhook', cpu: 28, mem: '204MB', memPct: 49, tasks: 5 },
  { id: 'flint', name: 'Flint', role: 'Infrastructure Engineer', tier: 'Crafter Tier', department: 'Platform', phase: 'Planning', personality: 'Automation obsessed — Docker, CI/CD, deployment scripts.', initial: 'F', avatar: '/workers/flint.png', status: 'offline', doing: 'Offline', cpu: 0, mem: '0MB', memPct: 0, tasks: 0 },
  { id: 'sentinel', name: 'Sentinel', role: 'Security Engineer', tier: 'Crafter Tier', department: 'Platform', phase: 'Planning', personality: 'Threat modeler — vulnerability scanning, auth hardening, security review.', initial: 'S', avatar: '/workers/sentinel.png', status: 'online', doing: 'Scanning for CVEs', cpu: 35, mem: '196MB', memPct: 45, tasks: 4 },
]

export const departmentColor: Record<Department, string> = {
  Leadership: 'bg-primary',
  Product: 'bg-success',
  Engineering: 'bg-warning',
  Platform: 'bg-info',
}

export type Mission = {
  id: string
  name: string
  phase: string
  progress: number
  worker: string
  updated: string
}

export const missions: Mission[] = [
  { id: 'm1', name: 'Implement Auth API', phase: 'Implementation', progress: 68, worker: 'Sage', updated: '2m ago' },
  { id: 'm2', name: 'Optimize Database', phase: 'Verification', progress: 45, worker: 'Luna', updated: '9m ago' },
  { id: 'm3', name: 'Add Export Feature', phase: 'Planning', progress: 12, worker: 'Aria', updated: '15m ago' },
  { id: 'm4', name: 'Fix Memory Leak', phase: 'Investigation', progress: 30, worker: 'Echo', updated: '22m ago' },
  { id: 'm5', name: 'Write API Docs', phase: 'Planning', progress: 8, worker: 'Rex', updated: '1h ago' },
]

export type Project = {
  id: string
  name: string
  type: string
  status: 'Active' | 'Archived'
  missions: number
  workers: number
  updated: string
  progress: number
}

export const projects: Project[] = [
  { id: 'p1', name: 'AIC Platform', type: 'Backend System', status: 'Active', missions: 12, workers: 5, updated: '5m ago', progress: 62 },
  { id: 'p2', name: 'AIC IDE', type: 'Desktop Application', status: 'Active', missions: 8, workers: 4, updated: '43m ago', progress: 41 },
  { id: 'p3', name: 'AIC Docs', type: 'Documentation', status: 'Active', missions: 3, workers: 2, updated: '2h ago', progress: 77 },
  { id: 'p4', name: 'AIC Website', type: 'Marketing Site', status: 'Active', missions: 4, workers: 2, updated: '1d ago', progress: 88 },
  { id: 'p5', name: 'AIC Mobile', type: 'Consumer App', status: 'Active', missions: 6, workers: 3, updated: '3h ago', progress: 24 },
  { id: 'p6', name: 'Internal Tools', type: 'Internal', status: 'Archived', missions: 5, workers: 2, updated: '3d ago', progress: 100 },
]

export type EventType = 'mission' | 'worker' | 'approval' | 'system'

export type TimelineEvent = {
  id: string
  time: string
  type: EventType
  title: string
  detail?: string
  actor: string
}

export const timelineEvents: TimelineEvent[] = [
  { id: 'e1', time: '22:41', type: 'mission', title: 'Mission "Implement Auth API" moved to Implementation', actor: 'Sage' },
  { id: 'e2', time: '22:33', type: 'worker', title: 'Worker Sage completed task "Code Review"', actor: 'Sage' },
  { id: 'e3', time: '22:20', type: 'system', title: 'Pipeline "Deploy Staging" started', actor: 'Hermes' },
  { id: 'e4', time: '22:04', type: 'approval', title: 'Approval requested: "Production Deployment"', detail: 'Requires action', actor: 'Hermes' },
  { id: 'e5', time: '21:56', type: 'worker', title: 'Worker Luna went idle', actor: 'Luna' },
  { id: 'e6', time: '21:32', type: 'mission', title: 'Mission "Optimize Database" verification passed', actor: 'Echo' },
  { id: 'e7', time: '21:10', type: 'worker', title: 'Worker Aria created new mission "Add Export Feature"', actor: 'Aria' },
]

export type Provider = {
  id: string
  name: string
  status: 'ACTIVE' | 'INACTIVE'
  endpoint: string
  thinker: string
  crafter: string
  sprinter: string
}

export const providers: Provider[] = [
  { id: 'v1', name: 'VansRouter', status: 'ACTIVE', endpoint: 'https://api.aicompany.bic.io/v1', thinker: 'oc/mimo-v2.5-free', crafter: 'oc/deepseek-v4-flash-free', sprinter: 'mmf/mimo-auto' },
  { id: 'v2', name: 'Deepseek V4 Flash', status: 'ACTIVE', endpoint: 'https://api.deepseek.com/v1', thinker: 'deepseek-v4-flash', crafter: 'deepseek-v4-flash', sprinter: 'deepseek-chat' },
  { id: 'v3', name: 'OpenAI Compatible', status: 'INACTIVE', endpoint: 'https://api.openai.com/v1', thinker: 'gpt-4o', crafter: 'gpt-4o-mini', sprinter: 'gpt-4o-mini' },
]

export const statusColor: Record<Status, string> = {
  online: 'bg-success',
  busy: 'bg-warning',
  idle: 'bg-muted-foreground',
  offline: 'bg-destructive',
}

export const statusLabel: Record<Status, string> = {
  online: 'Online',
  busy: 'Busy',
  idle: 'Idle',
  offline: 'Offline',
}
