/**
 * SkillsView — Skill management UI.
 *
 * Lists all registered skills, allows toggling, assigning workers,
 * and creating custom skills. Matches AIC IDE dark theme.
 */
import { useState, useEffect } from 'react'
import {
  Plus, Search, ToggleLeft, ToggleRight, Users, Trash2,
  RefreshCw, BookOpen, Shield, Code, Server, Wrench,
} from 'lucide-react'
import { Card, PageHeader, Badge } from './kit'
import { cn } from '../lib/utils'
import { skillsApi, type SkillRecord } from '../lib/api/skills'

const CATEGORY_ICONS: Record<string, React.ComponentType<{ className?: string }>> = {
  'software-development': Code,
  'security': Shield,
  'devops': Server,
  'custom': Wrench,
}

const CATEGORY_LABELS: Record<string, string> = {
  devops: 'DevOps',
}

const WORKER_OPTIONS = [
  'hermes', 'rex', 'pm', 'research', 'designer', 'documentation',
  'architect', 'backend', 'frontend', 'qa', 'performance', 'database',
  'nexus', 'flint', 'security', 'coding', 'debugger',
]

export function SkillsView() {
  const [skills, setSkills] = useState<SkillRecord[]>([])
  const [loading, setLoading] = useState(true)
  const [query, setQuery] = useState('')
  const [showCreate, setShowCreate] = useState(false)
  const [editingSkill, setEditingSkill] = useState<SkillRecord | null>(null)

  const load = async () => {
    try {
      setLoading(true)
      setSkills(await skillsApi.list())
    } catch (e) {
      console.error('Failed to load skills', e)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { void load() }, [])

  const handleToggle = async (skill: SkillRecord) => {
    try {
      await skillsApi.toggle(skill.skill_id, !skill.is_enabled)
      setSkills(prev => prev.map(s => s.skill_id === skill.skill_id ? { ...s, is_enabled: !s.is_enabled } : s))
    } catch (e) { console.error(e) }
  }

  const handleDelete = async (skill: SkillRecord) => {
    if (skill.source === 'built-in') return
    try {
      await skillsApi.delete(skill.skill_id)
      setSkills(prev => prev.filter(s => s.skill_id !== skill.skill_id))
    } catch (e) { console.error(e) }
  }

  const handleReseed = async () => {
    try {
      await skillsApi.reseed()
      await load()
    } catch (e) { console.error(e) }
  }

  const filtered = skills.filter(s =>
    !query || s.name.toLowerCase().includes(query.toLowerCase()) ||
    s.skill_id.toLowerCase().includes(query.toLowerCase()) ||
    s.category.toLowerCase().includes(query.toLowerCase())
  )

  const categories = Array.from(new Set(skills.map(s => s.category)))

  return (
    <div className="min-h-full">
      <PageHeader
        title="Skill Registry"
        subtitle={`${skills.length} skills registered · ${skills.filter(s => s.is_enabled).length} enabled`}
        actions={
          <>
            <button onClick={() => setShowCreate(!showCreate)}
              className="inline-flex items-center gap-2 rounded-lg bg-primary/15 px-3 py-1.5 text-xs font-medium text-primary hover:bg-primary/25">
              <Plus className="size-3.5" /> New Skill
            </button>
            <button onClick={handleReseed}
              className="inline-flex items-center gap-2 rounded-lg border border-border px-3 py-1.5 text-xs font-medium text-muted-foreground hover:text-foreground">
              <RefreshCw className="size-3.5" /> Re-seed
            </button>
          </>
        }
      />

      <div className="p-6 space-y-6">
        {/* Search */}
        <div className="flex items-center gap-3 rounded-lg border border-border bg-card px-3 py-2 max-w-md focus-within:border-primary/50">
          <Search className="size-4 text-muted-foreground" />
          <input value={query} onChange={e => setQuery(e.target.value)}
            placeholder="Search skills…"
            className="flex-1 bg-transparent text-sm outline-none placeholder:text-muted-foreground/60" />
        </div>

        {/* Create form */}
        {showCreate && <CreateSkillForm onClose={() => setShowCreate(false)} onCreated={load} />}

        {/* Skills by category */}
        {loading ? (
          <div className="py-12 text-center text-sm text-muted-foreground">Loading skills…</div>
        ) : (
          categories.map(cat => {
            const catSkills = filtered.filter(s => s.category === cat)
            if (catSkills.length === 0) return null
            const Icon = CATEGORY_ICONS[cat] || BookOpen
            return (
              <div key={cat}>
                <div className="mb-3 flex items-center gap-2">
                  <Icon className="size-4 text-primary" />
                  <h2 className="text-sm font-semibold capitalize">{CATEGORY_LABELS[cat] || cat.replace('-', ' ')}</h2>
                  <span className="text-xs text-muted-foreground">({catSkills.length})</span>
                </div>
                <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
                  {catSkills.map(skill => (
                    <SkillCard key={skill.skill_id} skill={skill}
                      onToggle={() => handleToggle(skill)}
                      onDelete={() => handleDelete(skill)}
                      onEdit={() => setEditingSkill(editingSkill?.skill_id === skill.skill_id ? null : skill)}
                    />
                  ))}
                </div>
              </div>
            )
          })
        )}

        {/* Edit panel */}
        {editingSkill && (
          <EditSkillPanel skill={editingSkill}
            onClose={() => setEditingSkill(null)}
            onUpdated={load}
          />
        )}
      </div>
    </div>
  )
}

// ── Skill Card ───────────────────────────────────────────

function SkillCard({ skill, onToggle, onDelete, onEdit }: {
  skill: SkillRecord
  onToggle: () => void
  onDelete: () => void
  onEdit: () => void
}) {
  return (
    <Card className={cn("relative transition-all", !skill.is_enabled && "opacity-50")}>
      <div className="flex items-start justify-between gap-2">
        <div className="min-w-0 flex-1" onClick={onEdit}>
          <p className="text-sm font-semibold truncate cursor-pointer hover:text-primary">{skill.name}</p>
          <p className="mt-0.5 text-[11px] text-muted-foreground truncate">{skill.description}</p>
        </div>
        <button onClick={onToggle} className="shrink-0" title={skill.is_enabled ? 'Disable' : 'Enable'}>
          {skill.is_enabled
            ? <ToggleRight className="size-5 text-success" />
            : <ToggleLeft className="size-5 text-muted-foreground" />}
        </button>
      </div>

      <div className="mt-3 flex flex-wrap gap-1">
        {(skill.assigned_workers || []).slice(0, 5).map(w => (
          <Badge key={w} tone="primary" className="text-[9px]">{w}</Badge>
        ))}
        {(skill.assigned_workers || []).length > 5 && (
          <span className="text-[9px] text-muted-foreground">+{skill.assigned_workers.length - 5}</span>
        )}
      </div>

      <div className="mt-2 flex items-center justify-between">
        <div className="flex items-center gap-1.5">
          <Badge tone={skill.source === 'built-in' ? 'warning' : 'success'} className="text-[9px]">{skill.source}</Badge>
          <code className="text-[9px] text-muted-foreground font-mono">{skill.skill_id}</code>
        </div>
        {skill.source !== 'built-in' && (
          <button onClick={onDelete} className="text-muted-foreground hover:text-destructive">
            <Trash2 className="size-3" />
          </button>
        )}
      </div>
    </Card>
  )
}

// ── Create Form ──────────────────────────────────────────

function CreateSkillForm({ onClose, onCreated }: { onClose: () => void; onCreated: () => void }) {
  const [form, setForm] = useState({
    skill_id: '', name: '', description: '', category: 'custom',
    instructions: '', assigned_workers: [] as string[],
  })
  const [saving, setSaving] = useState(false)

  const handleSave = async () => {
    if (!form.skill_id || !form.name || !form.instructions) return
    setSaving(true)
    try {
      await skillsApi.create(form)
      onCreated()
      onClose()
    } catch (e) { console.error(e) }
    finally { setSaving(false) }
  }

  return (
    <Card className="space-y-3">
      <h3 className="text-sm font-semibold">Create Custom Skill</h3>
      <div className="grid gap-3 sm:grid-cols-2">
        <input value={form.skill_id} onChange={e => setForm(f => ({ ...f, skill_id: e.target.value }))}
          placeholder="skill-id (e.g. api-rate-limiting)" className="rounded-lg border border-border bg-background px-3 py-2 text-xs outline-none focus:border-primary" />
        <input value={form.name} onChange={e => setForm(f => ({ ...f, name: e.target.value }))}
          placeholder="Display Name" className="rounded-lg border border-border bg-background px-3 py-2 text-xs outline-none focus:border-primary" />
      </div>
      <input value={form.description} onChange={e => setForm(f => ({ ...f, description: e.target.value }))}
        placeholder="Short description" className="w-full rounded-lg border border-border bg-background px-3 py-2 text-xs outline-none focus:border-primary" />
      <textarea value={form.instructions} onChange={e => setForm(f => ({ ...f, instructions: e.target.value }))}
        placeholder="Instructions for the worker (what to do when this skill is active)"
        rows={3} className="w-full rounded-lg border border-border bg-background px-3 py-2 text-xs outline-none focus:border-primary resize-none" />
      <div>
        <p className="text-[10px] text-muted-foreground mb-1">Assign to workers:</p>
        <div className="flex flex-wrap gap-1">
          {WORKER_OPTIONS.map(w => {
            const active = form.assigned_workers.includes(w)
            return (
              <button key={w} onClick={() => setForm(f => ({
                ...f,
                assigned_workers: active ? f.assigned_workers.filter(x => x !== w) : [...f.assigned_workers, w],
              }))}
                className={cn("rounded px-2 py-0.5 text-[10px] transition-colors",
                  active ? "bg-primary/20 text-primary" : "bg-muted text-muted-foreground hover:text-foreground"
                )}>{w}</button>
            )
          })}
        </div>
      </div>
      <div className="flex gap-2">
        <button onClick={handleSave} disabled={saving || !form.skill_id || !form.name || !form.instructions}
          className="rounded-lg bg-primary px-4 py-1.5 text-xs font-medium text-primary-foreground hover:bg-primary/90 disabled:opacity-50">
          {saving ? 'Saving…' : 'Create Skill'}
        </button>
        <button onClick={onClose} className="rounded-lg border border-border px-4 py-1.5 text-xs text-muted-foreground hover:text-foreground">
          Cancel
        </button>
      </div>
    </Card>
  )
}

// ── Edit Panel ───────────────────────────────────────────

function EditSkillPanel({ skill, onClose, onUpdated }: {
  skill: SkillRecord; onClose: () => void; onUpdated: () => void
}) {
  const [workers, setWorkers] = useState<string[]>(skill.assigned_workers || [])
  const [saving, setSaving] = useState(false)

  const handleSave = async () => {
    setSaving(true)
    try {
      await skillsApi.assignWorkers(skill.skill_id, workers)
      onUpdated()
      onClose()
    } catch (e) { console.error(e) }
    finally { setSaving(false) }
  }

  return (
    <Card className="space-y-3">
      <div className="flex items-center justify-between">
        <h3 className="text-sm font-semibold">{skill.name}</h3>
        <button onClick={onClose} className="text-muted-foreground hover:text-foreground text-xs">Close</button>
      </div>
      <p className="text-xs text-muted-foreground">{skill.description}</p>
      <div className="rounded-lg bg-muted/30 p-3">
        <p className="text-[10px] text-muted-foreground mb-1 font-semibold">Instructions:</p>
        <p className="text-xs font-mono whitespace-pre-wrap">{skill.instructions}</p>
      </div>
      <div>
        <p className="text-[10px] text-muted-foreground mb-1">Assigned Workers:</p>
        <div className="flex flex-wrap gap-1">
          {WORKER_OPTIONS.map(w => {
            const active = workers.includes(w)
            return (
              <button key={w} onClick={() => setWorkers(prev =>
                active ? prev.filter(x => x !== w) : [...prev, w]
              )}
                className={cn("rounded px-2 py-0.5 text-[10px] transition-colors",
                  active ? "bg-primary/20 text-primary" : "bg-muted text-muted-foreground hover:text-foreground"
                )}>{w}</button>
            )
          })}
        </div>
      </div>
      <button onClick={handleSave} disabled={saving}
        className="rounded-lg bg-primary px-4 py-1.5 text-xs font-medium text-primary-foreground hover:bg-primary/90 disabled:opacity-50">
        {saving ? 'Saving…' : 'Save Assignments'}
      </button>
    </Card>
  )
}
