import { useState, useEffect, useCallback } from 'react'
import { Plus, RefreshCw, Trash2, Bell, BellOff, Zap, X } from 'lucide-react'
import { Card, PageHeader, Badge } from './kit'
import { cn } from '../lib/utils'
import {
  automationApi,
  type EventHookRecord,
  type TriggerRecord,
  type NotificationRecord,
  type ActionType,
} from '../lib/api/automation'

const actionTypes: ActionType[] = ['notify', 'job', 'webhook', 'script']

const levelTone: Record<string, 'muted' | 'primary' | 'success' | 'warning' | 'destructive'> = {
  info: 'primary',
  warning: 'warning',
  error: 'destructive',
  success: 'success',
}

export function AutomationView() {
  const [hooks, setHooks] = useState<EventHookRecord[]>([])
  const [triggers, setTriggers] = useState<TriggerRecord[]>([])
  const [notifications, setNotifications] = useState<NotificationRecord[]>([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  // Create hook form
  const [showCreateHook, setShowCreateHook] = useState(false)
  const [hookName, setHookName] = useState('')
  const [hookEventType, setHookEventType] = useState('')
  const [hookActionType, setHookActionType] = useState<ActionType>('notify')
  const [hookDesc, setHookDesc] = useState('')

  // Create trigger form
  const [showCreateTrigger, setShowCreateTrigger] = useState(false)
  const [triggerName, setTriggerName] = useState('')
  const [triggerCondition, setTriggerCondition] = useState('{}')
  const [triggerAction, setTriggerAction] = useState('{}')
  const [triggerDesc, setTriggerDesc] = useState('')

  const loadHooks = useCallback(async () => {
    try {
      const data = await automationApi.listHooks()
      setHooks(data)
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : String(e))
    }
  }, [])

  const loadTriggers = useCallback(async () => {
    try {
      const data = await automationApi.listTriggers()
      setTriggers(data)
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : String(e))
    }
  }, [])

  const loadNotifications = useCallback(async () => {
    try {
      const data = await automationApi.listNotifications()
      setNotifications(data)
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : String(e))
    }
  }, [])

  useEffect(() => {
    loadHooks()
    loadTriggers()
    loadNotifications()
  }, [loadHooks, loadTriggers, loadNotifications])

  const handleCreateHook = async () => {
    if (!hookName.trim() || !hookEventType.trim()) return
    setLoading(true)
    setError(null)
    try {
      await automationApi.createHook({
        name: hookName,
        event_type: hookEventType,
        action_type: hookActionType,
        description: hookDesc || undefined,
      })
      setShowCreateHook(false)
      setHookName('')
      setHookEventType('')
      setHookDesc('')
      await loadHooks()
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : String(e))
    } finally {
      setLoading(false)
    }
  }

  const handleCreateTrigger = async () => {
    if (!triggerName.trim()) return
    setLoading(true)
    setError(null)
    try {
      const condition = JSON.parse(triggerCondition)
      const action = JSON.parse(triggerAction)
      await automationApi.createTrigger({
        name: triggerName,
        condition,
        action,
        description: triggerDesc || undefined,
      })
      setShowCreateTrigger(false)
      setTriggerName('')
      setTriggerCondition('{}')
      setTriggerAction('{}')
      setTriggerDesc('')
      await loadTriggers()
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : String(e))
    } finally {
      setLoading(false)
    }
  }

  const handleDeleteHook = async (id: string) => {
    try {
      await automationApi.deleteHook(id)
      await loadHooks()
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : String(e))
    }
  }

  const handleDeleteTrigger = async (id: string) => {
    try {
      await automationApi.deleteTrigger(id)
      await loadTriggers()
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : String(e))
    }
  }

  const handleMarkRead = async (id: string) => {
    try {
      await automationApi.markRead(id)
      await loadNotifications()
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : String(e))
    }
  }

  const handleMarkAllRead = async () => {
    try {
      await automationApi.markAllRead()
      await loadNotifications()
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : String(e))
    }
  }

  const unreadCount = notifications.filter((n) => !n.isRead).length

  return (
    <div>
      <PageHeader
        title="Automation"
        subtitle="Event hooks, triggers, and notification management."
        actions={
          <div className="flex gap-2">
            <button
              onClick={() => setShowCreateHook(true)}
              className="inline-flex items-center gap-2 rounded-lg bg-primary px-3 py-1.5 text-sm font-medium text-primary-foreground hover:bg-primary/90"
            >
              <Plus className="size-4" /> New Hook
            </button>
            <button
              onClick={() => setShowCreateTrigger(true)}
              className="inline-flex items-center gap-2 rounded-lg border border-primary/50 px-3 py-1.5 text-sm font-medium text-primary hover:bg-primary/10"
            >
              <Plus className="size-4" /> New Trigger
            </button>
          </div>
        }
      />

      <div className="p-6 space-y-3">
        {error && (
          <Card className="border-destructive/40 bg-destructive/5 text-sm text-destructive flex items-center justify-between">
            <span>{error}</span>
            <button onClick={() => setError(null)}><X className="size-4" /></button>
          </Card>
        )}

        {/* Create hook form */}
        {showCreateHook && (
          <Card className="space-y-3">
            <h3 className="text-sm font-semibold">Create Event Hook</h3>
            <div className="grid gap-3 sm:grid-cols-2">
              <div>
                <label className="text-[11px] uppercase tracking-wide text-muted-foreground">Name</label>
                <input
                  value={hookName}
                  onChange={(e) => setHookName(e.target.value)}
                  placeholder="Hook name"
                  className="mt-1 w-full rounded-md border border-border bg-background px-3 py-1.5 text-sm outline-none focus:border-primary"
                />
              </div>
              <div>
                <label className="text-[11px] uppercase tracking-wide text-muted-foreground">Event Type</label>
                <input
                  value={hookEventType}
                  onChange={(e) => setHookEventType(e.target.value)}
                  placeholder="e.g. job.completed, task.failed"
                  className="mt-1 w-full rounded-md border border-border bg-background px-3 py-1.5 text-sm outline-none focus:border-primary"
                />
              </div>
              <div>
                <label className="text-[11px] uppercase tracking-wide text-muted-foreground">Action Type</label>
                <select
                  value={hookActionType}
                  onChange={(e) => setHookActionType(e.target.value as ActionType)}
                  className="mt-1 w-full rounded-md border border-border bg-background px-3 py-1.5 text-sm outline-none focus:border-primary"
                >
                  {actionTypes.map((t) => <option key={t} value={t}>{t}</option>)}
                </select>
              </div>
              <div>
                <label className="text-[11px] uppercase tracking-wide text-muted-foreground">Description</label>
                <input
                  value={hookDesc}
                  onChange={(e) => setHookDesc(e.target.value)}
                  placeholder="Optional description"
                  className="mt-1 w-full rounded-md border border-border bg-background px-3 py-1.5 text-sm outline-none focus:border-primary"
                />
              </div>
            </div>
            <div className="flex gap-2">
              <button
                onClick={handleCreateHook}
                disabled={loading}
                className="rounded-lg bg-primary px-3 py-1.5 text-sm font-medium text-primary-foreground hover:bg-primary/90 disabled:opacity-50"
              >
                {loading ? 'Creating...' : 'Create Hook'}
              </button>
              <button onClick={() => setShowCreateHook(false)} className="rounded-lg border border-border px-3 py-1.5 text-sm hover:bg-muted">
                Cancel
              </button>
            </div>
          </Card>
        )}

        {/* Create trigger form */}
        {showCreateTrigger && (
          <Card className="space-y-3">
            <h3 className="text-sm font-semibold">Create Trigger</h3>
            <div className="grid gap-3 sm:grid-cols-2">
              <div>
                <label className="text-[11px] uppercase tracking-wide text-muted-foreground">Name</label>
                <input
                  value={triggerName}
                  onChange={(e) => setTriggerName(e.target.value)}
                  placeholder="Trigger name"
                  className="mt-1 w-full rounded-md border border-border bg-background px-3 py-1.5 text-sm outline-none focus:border-primary"
                />
              </div>
              <div>
                <label className="text-[11px] uppercase tracking-wide text-muted-foreground">Description</label>
                <input
                  value={triggerDesc}
                  onChange={(e) => setTriggerDesc(e.target.value)}
                  placeholder="Optional description"
                  className="mt-1 w-full rounded-md border border-border bg-background px-3 py-1.5 text-sm outline-none focus:border-primary"
                />
              </div>
              <div>
                <label className="text-[11px] uppercase tracking-wide text-muted-foreground">Condition (JSON)</label>
                <textarea
                  value={triggerCondition}
                  onChange={(e) => setTriggerCondition(e.target.value)}
                  rows={3}
                  className="mt-1 w-full rounded-md border border-border bg-background px-3 py-1.5 font-mono text-xs outline-none focus:border-primary"
                />
              </div>
              <div>
                <label className="text-[11px] uppercase tracking-wide text-muted-foreground">Action (JSON)</label>
                <textarea
                  value={triggerAction}
                  onChange={(e) => setTriggerAction(e.target.value)}
                  rows={3}
                  className="mt-1 w-full rounded-md border border-border bg-background px-3 py-1.5 font-mono text-xs outline-none focus:border-primary"
                />
              </div>
            </div>
            <div className="flex gap-2">
              <button
                onClick={handleCreateTrigger}
                disabled={loading}
                className="rounded-lg bg-primary px-3 py-1.5 text-sm font-medium text-primary-foreground hover:bg-primary/90 disabled:opacity-50"
              >
                {loading ? 'Creating...' : 'Create Trigger'}
              </button>
              <button onClick={() => setShowCreateTrigger(false)} className="rounded-lg border border-border px-3 py-1.5 text-sm hover:bg-muted">
                Cancel
              </button>
            </div>
          </Card>
        )}

        <div className="grid gap-4 lg:grid-cols-2">
          {/* Event Hooks */}
          <Card>
            <div className="flex items-center justify-between mb-3">
              <h3 className="text-sm font-semibold flex items-center gap-2"><Zap className="size-4" /> Event Hooks ({hooks.length})</h3>
              <button onClick={loadHooks} className="text-muted-foreground hover:text-foreground">
                <RefreshCw className="size-4" />
              </button>
            </div>
            {hooks.length === 0 ? (
              <p className="text-xs text-muted-foreground">No hooks configured.</p>
            ) : (
              <div className="space-y-2">
                {hooks.map((h) => (
                  <div key={h.id} className="flex items-center justify-between rounded-lg border border-border bg-background/50 p-3">
                    <div className="min-w-0">
                      <div className="flex items-center gap-2">
                        <span className="text-sm font-medium">{h.name}</span>
                        <Badge tone="muted">{h.actionType}</Badge>
                        {h.isEnabled ? <Badge tone="success">Active</Badge> : <Badge tone="muted">Disabled</Badge>}
                      </div>
                      <p className="text-xs text-muted-foreground mt-0.5">Event: {h.eventType}</p>
                      <p className="text-[10px] text-muted-foreground">Fired: {h.fireCount}x</p>
                    </div>
                    <button
                      onClick={() => handleDeleteHook(h.id)}
                      className="inline-flex items-center gap-1 rounded-md border border-destructive/40 px-2 py-1 text-xs text-destructive hover:bg-destructive/10 shrink-0"
                    >
                      <Trash2 className="size-3" />
                    </button>
                  </div>
                ))}
              </div>
            )}
          </Card>

          {/* Triggers */}
          <Card>
            <div className="flex items-center justify-between mb-3">
              <h3 className="text-sm font-semibold flex items-center gap-2"><Zap className="size-4" /> Triggers ({triggers.length})</h3>
              <button onClick={loadTriggers} className="text-muted-foreground hover:text-foreground">
                <RefreshCw className="size-4" />
              </button>
            </div>
            {triggers.length === 0 ? (
              <p className="text-xs text-muted-foreground">No triggers configured.</p>
            ) : (
              <div className="space-y-2">
                {triggers.map((t) => (
                  <div key={t.id} className="flex items-center justify-between rounded-lg border border-border bg-background/50 p-3">
                    <div className="min-w-0">
                      <div className="flex items-center gap-2">
                        <span className="text-sm font-medium">{t.name}</span>
                        {t.isEnabled ? <Badge tone="success">Active</Badge> : <Badge tone="muted">Disabled</Badge>}
                      </div>
                      <p className="text-[10px] font-mono text-muted-foreground mt-0.5">
                        Condition: {JSON.stringify(t.condition)}
                      </p>
                      <p className="text-[10px] text-muted-foreground">Fired: {t.fireCount}x</p>
                    </div>
                    <button
                      onClick={() => handleDeleteTrigger(t.id)}
                      className="inline-flex items-center gap-1 rounded-md border border-destructive/40 px-2 py-1 text-xs text-destructive hover:bg-destructive/10 shrink-0"
                    >
                      <Trash2 className="size-3" />
                    </button>
                  </div>
                ))}
              </div>
            )}
          </Card>
        </div>

        {/* Notifications */}
        <Card>
          <div className="flex items-center justify-between mb-3">
            <h3 className="text-sm font-semibold flex items-center gap-2">
              <Bell className="size-4" /> Notifications
              {unreadCount > 0 && <Badge tone="destructive">{unreadCount} unread</Badge>}
            </h3>
            <div className="flex items-center gap-2">
              {unreadCount > 0 && (
                <button
                  onClick={handleMarkAllRead}
                  className="inline-flex items-center gap-1 rounded-md border border-primary/50 px-2 py-1 text-xs font-medium text-primary hover:bg-primary/10"
                >
                  <BellOff className="size-3" /> Mark All Read
                </button>
              )}
              <button onClick={loadNotifications} className="text-muted-foreground hover:text-foreground">
                <RefreshCw className="size-4" />
              </button>
            </div>
          </div>
          {notifications.length === 0 ? (
            <p className="text-xs text-muted-foreground">No notifications.</p>
          ) : (
            <div className="space-y-2">
              {notifications.map((n) => (
                <div
                  key={n.id}
                  className={cn(
                    'flex items-start justify-between rounded-lg border p-3',
                    n.isRead ? 'border-border bg-background/50 opacity-60' : 'border-primary/30 bg-primary/5',
                  )}
                >
                  <div className="min-w-0">
                    <div className="flex items-center gap-2">
                      <span className="text-sm font-medium">{n.title}</span>
                      <Badge tone={levelTone[n.level] || 'muted'}>{n.level}</Badge>
                      {n.source && <Badge tone="muted">{n.source}</Badge>}
                    </div>
                    <p className="mt-1 text-xs text-muted-foreground">{n.message}</p>
                    <p className="mt-1 text-[10px] text-muted-foreground">{new Date(n.createdAt).toLocaleString()}</p>
                  </div>
                  {!n.isRead && (
                    <button
                      onClick={() => handleMarkRead(n.id)}
                      className="inline-flex items-center gap-1 rounded-md border border-border px-2 py-1 text-xs hover:bg-muted shrink-0"
                    >
                      <BellOff className="size-3" /> Read
                    </button>
                  )}
                </div>
              ))}
            </div>
          )}
        </Card>
      </div>
    </div>
  )
}
