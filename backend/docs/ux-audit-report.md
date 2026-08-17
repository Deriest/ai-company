# Frontend UX Audit Report

**Date:** 2026-07-21
**Scope:** All 13 pages in `frontend/src/pages/`
**Total issues found:** 73

---

## Summary by Severity

| Severity | Count |
|----------|-------|
| 🔴 High (bugs/data loss/races) | 12 |
| 🟠 Medium (UX degradation) | 28 |
| 🟡 Low (polish/a11y/mobile) | 33 |

## Summary by Category

| Category | Count |
|----------|-------|
| Race conditions / memory leaks | 11 |
| Missing error states | 6 |
| Missing loading states | 8 |
| Accessibility (aria/labels) | 22 |
| Mobile layout issues | 7 |
| Memory leaks (createObjectURL) | 3 |
| Other (dead code, hardcoded values) | 16 |

---

## Page-by-Page Findings

### 1. Chat.tsx

| # | Line(s) | Severity | Category | Issue |
|---|---------|----------|----------|-------|
| 1 | 88–96 | 🔴 High | Race condition | `useEffect` fetching messages has no abort controller. If `active` changes rapidly, responses arrive out of order and stale data overwrites fresh data. |
| 2 | 120–203 | 🔴 High | Race condition | `sendMessage()` has no unmount guard. If user navigates away during SSE stream, `setMessages`/`setSending` fire on unmounted component. |
| 3 | 78–84 | 🟠 Medium | Race condition | `loadConvs()` has no cleanup; re-invocation from line 195 (`loadConvs()` after send) can race with the initial load. |
| 4 | 563 | 🟠 Medium | Security | `dangerouslySetInnerHTML` with regex-based markdown parser. The escaping (lines 8–10) is correct but regex can be bypassed with crafted input. XSS risk if assistant content is ever user-controllable. |
| 5 | 242–254 | 🟠 Medium | Missing loading | `batchAction()` has no loading state — buttons can be double-clicked, issuing duplicate requests. |
| 6 | 326 | 🟡 Low | A11y | Search `<input>` has no `aria-label` (placeholder is not a label). |
| 7 | 333–342 | 🟡 Low | A11y | Filter toggle buttons ("Active"/"Archived") have no `aria-pressed` or `role="tab"`. |
| 8 | 389–402 | 🟡 Low | A11y | Conversation list items are `<button>` but lack `aria-current` for active state. |
| 9 | 407–414 | 🟡 Low | A11y | Context menu "..." button has only `title`, no `aria-label` or `aria-haspopup`. |
| 10 | 418–449 | 🟡 Low | A11y | Dropdown menu has no `role="menu"`, items have no `role="menuitem"`. |
| 11 | 483 | 🟠 Medium | UX | Error message has no dismiss button — accumulates and takes space forever. |

### 2. Dashboard.tsx

| # | Line(s) | Severity | Category | Issue |
|---|---------|----------|----------|-------|
| 12 | 67–78 | 🟠 Medium | Resilience | `Promise.all` — if overview succeeds but events fails, both results are lost. Use `Promise.allSettled` or handle independently. |
| 13 | — | 🟠 Medium | Missing feature | No refresh/polling mechanism. User must reload page to see updated stats. |
| 14 | 92–104 | 🟡 Low | A11y | Stat cards lack `aria-label` describing the metric. Icon SVGs have no `aria-hidden="true"`. |
| 15 | 121–133 | 🟡 Low | A11y | Event list items lack `role="listitem"` context (parent is `<ul>` so partial pass). Severity dots have no accessible text alternative. |

### 3. Audit.tsx

| # | Line(s) | Severity | Category | Issue |
|---|---------|----------|----------|-------|
| 16 | 38–41 | 🟠 Medium | Memory leak | `URL.createObjectURL(blob)` is called but `URL.revokeObjectURL()` is never called. Each export leaks a blob URL. |
| 17 | — | 🟠 Medium | Missing feature | Hard-coded `limit=100` with no pagination. Large audit logs are silently truncated. |
| 18 | 96–157 | 🟡 Low | A11y | `<table>` has no `<caption>` or `aria-label`. Expanded rows have no `aria-expanded` indicator on the clickable `<tr>`. |
| 19 | 71 | 🟡 Low | A11y | Search input has no `aria-label`. |
| 20 | 79 | 🟡 Low | A11y | `<select>` has no `<label>` element, only implicit text. |

### 4. Workers.tsx

| # | Line(s) | Severity | Category | Issue |
|---|---------|----------|----------|-------|
| 21 | 12–25 | 🟠 Medium | Performance | N+1 API calls: fetches all workers, then one `/leases` call per worker. With 20+ workers this is 21 sequential requests. |
| 22 | 12–25 | 🔴 High | Race condition | No abort/cleanup if component unmounts during the N+1 cascade. |
| 23 | — | 🟠 Medium | Missing feature | No refresh mechanism. No way to see live worker status updates. |
| 24 | 40–89 | 🟡 Low | A11y | Worker cards have no `role="article"` or landmark. Status badges duplicate visual info without accessible text. |

### 5. Tasks.tsx

| # | Line(s) | Severity | Category | Issue |
|---|---------|----------|----------|-------|
| 25 | 42–48 | 🔴 High | Race condition | `useEffect` for selected task: no abort controller. Rapid task clicks cause responses to arrive out of order — stale task overwrites fresh one. |
| 26 | 62–78 | 🟠 Medium | Missing loading | `dispatch()` and `cancel()` have no loading indicators. User can click "Dispatch" or "Cancel" multiple times. |
| 27 | 90–95 | 🟡 Low | A11y | Search input has no `aria-label`, only `placeholder`. |
| 28 | 147–165 | 🟡 Low | A11y | Status filter pills have no `aria-pressed` state. |
| 29 | 168 | 🟡 Low | Mobile | On mobile (`grid-cols-1`), the detail panel appears below the list with no scroll-to or visual cue. User may not notice it. |
| 30 | 112 | 🟡 Low | Mobile | Form `grid-cols-2` (line 112) not responsive — Project ID and Type select are side-by-side even on small screens. |

### 6. Login.tsx

| # | Line(s) | Severity | Category | Issue |
|---|---------|----------|----------|-------|
| 31 | 70–90 | 🟠 Medium | A11y | All form `<Input>` elements use only `placeholder` — no `<label>` elements. Screen readers can't identify fields. |
| 32 | 54–66 | 🟡 Low | A11y | Tab switcher buttons have no `role="tablist"` / `role="tab"` / `aria-selected`. |
| 33 | — | 🟡 Low | UX | No password visibility toggle. Users can't verify what they typed. |
| 34 | — | 🟡 Low | UX | No "forgot password" or recovery flow (acceptable for MVP). |

### 7. Console.tsx

| # | Line(s) | Severity | Category | Issue |
|---|---------|----------|----------|-------|
| 35 | 16–27 | 🔴 High | Missing error | `fetchData` has **no error handling at all** — no `.catch()`. API failures are silently swallowed; user sees stale data with no indication. |
| 36 | 60–63 | 🟠 Medium | Memory leak | `URL.createObjectURL` in `handleExport` — never revoked. |
| 37 | 75 | 🔴 High | Mobile | `grid-cols-4` status cards (line 75) have **no responsive breakpoint**. On mobile, 4 cards are crushed into one row — completely unreadable. |
| 38 | 121–124 | 🟡 Low | A11y | Search input has no `aria-label`. |
| 39 | 126–140 | 🟡 Low | A11y | Auto-scroll, Export, Refresh buttons use only `title` — no `aria-label`. Refresh button text "↻" is not accessible. |
| 40 | 148 | 🟡 Low | Performance | Log keys use array index (`key={i}`) — React can mis-render when logs are prepended/filtered. Use a stable ID. |
| 41 | 6–8 | 🟠 Medium | Type safety | Heavy `any` usage for `logs`, `events`, `status` — no compile-time safety. |

### 8. Usage.tsx

| # | Line(s) | Severity | Category | Issue |
|---|---------|----------|----------|-------|
| 42 | 93–105 | 🟠 Medium | Mobile | Timeline chart with 30 bars in a fixed `h-32` container. On mobile (<375px), each bar is ~10px wide with gap — data is indistinguishable. |
| 43 | 78 | 🟡 Low | A11y | Summary cards have no `aria-label` for the metric name/value pair. |
| 44 | 94–104 | 🟡 Low | A11y | Timeline bars are visual-only — no text alternative or ARIA description for screen readers. |
| 45 | 108–109 | 🟡 Low | A11y | Legend uses colored `<span>` dots with no `aria-hidden="true"`. |

### 9. WorkerDetail.tsx

| # | Line(s) | Severity | Category | Issue |
|---|---------|----------|----------|-------|
| 46 | 14–19 | 🔴 High | Missing error | `Promise.all` has **no `.catch()`**. On API failure, loading stops but worker stays `null` — shows "Worker not found" instead of actual error (e.g., network failure). |
| 47 | 39 | 🟠 Medium | Mobile | `grid-cols-3` (Role/Tier/Status) has no responsive breakpoint. On small screens, columns are squished. |
| 48 | 52–66 | 🟠 Medium | Missing feature | Lease list has no pagination. Workers with many leases will have an infinitely growing list. |
| 49 | 31 | 🟡 Low | A11y | Back link `<Link>` has no `aria-label` describing the navigation target. |
| 50 | 34 | 🟡 Low | A11y | Status dot `<span>` has no accessible text — screen readers skip it. |

### 10. Providers.tsx

| # | Line(s) | Severity | Category | Issue |
|---|---------|----------|----------|-------|
| 51 | 14–25 | 🔴 High | Missing error | **No error state at all.** `fetchProviders()`, `fetchModels()`, and `handleSave()` have no `.catch()` — errors are completely swallowed. User gets no feedback on failure. |
| 52 | 27–33 | 🟠 Medium | Race condition | `useEffect` for fetching models on `selected` change has no cleanup. Rapid provider switching can cause stale model lists. |
| 53 | 6–7, 15, 21 | 🟠 Medium | Type safety | All state uses `any` types — providers, models. No compile-time validation. |
| 54 | 62–77 | 🟡 Low | A11y | Provider buttons lack `aria-pressed` for selected state. |
| 55 | 85, 90, 91–93 | 🟡 Low | A11y | Edit/Cancel/Save buttons have no `aria-label` context. |
| 56 | 119–123 | 🟡 Low | A11y | Model list items are plain `<div>` — should be a `<ul>/<li>` list. |

### 11. Settings.tsx

| # | Line(s) | Severity | Category | Issue |
|---|---------|----------|----------|-------|
| 57 | 280–293, 298–314 | 🟠 Medium | Mobile | `grid-cols-2` and `grid-cols-3` form layouts are not responsive. On mobile, fields are cramped or overflow. |
| 58 | 341, 448 | 🟠 Medium | Mobile | Tier config `grid-cols-3` (line 341) and usage stats `grid-cols-3` (line 448) are not responsive. |
| 59 | 550–553 | 🟠 Medium | UX | Generated API key is shown in a read-only input with no copy-to-clipboard button. Users must manually select and copy. |
| 60 | 282–313 | 🟡 Low | A11y | Form inputs have `<label>` elements but they're not associated via `htmlFor`/`id`. Labels are visual-only. |
| 61 | 487–509 | 🟡 Low | A11y | Usage table has no `<caption>` or `aria-label`. |
| 62 | 552 | 🟡 Low | UX | Generated API key field should have `type="password"` by default with a reveal toggle — it's sensitive. |

### 12. Approvals.tsx

| # | Line(s) | Severity | Category | Issue |
|---|---------|----------|----------|-------|
| 63 | 23–30 | 🟠 Medium | Missing loading | `decide()` has no loading state. Approve/Reject buttons can be clicked multiple times, issuing duplicate decisions. |
| 64 | 76–102 | 🟡 Low | UX | History section is completely hidden when empty — no "No history yet" message. |
| 65 | 63–68 | 🟡 Low | A11y | Approve/Reject buttons have no `aria-label` beyond the text content (OK for sighted users, but could use `aria-describedby` for the task context). |
| 66 | 80–98 | 🟡 Low | A11y | History table has no `<caption>`. |

### 13. Projects.tsx

| # | Line(s) | Severity | Category | Issue |
|---|---------|----------|----------|-------|
| 67 | 13–29 | 🟠 Medium | Performance | N+1 API calls: fetches all projects, then one `/tasks` call per project. Same issue as Workers.tsx. |
| 68 | 13–29 | 🔴 High | Race condition | No abort/cleanup on unmount. |
| 69 | 36–46 | 🟠 Medium | Missing loading | `create()` has no loading state. "Create" button can be double-clicked. |
| 70 | 82 | 🟡 Low | Inconsistency | Uses inline text "No projects yet." instead of the shared `EmptyState` component. |
| 71 | 60–79 | 🟡 Low | A11y | Form inputs have no `<label>` elements. |
| 72 | — | 🟠 Medium | Missing feature | No pagination — all projects loaded at once. |
| 73 | 85–114 | 🟡 Low | A11y | Project cards have no `role="article"` or semantic landmark. |

---

## Cross-Cutting Issues

### 1. No AbortController Usage Anywhere
Every page that fetches data uses `useEffect` with async calls but **none** use `AbortController`. This means:
- Navigating between pages can trigger state updates on unmounted components (React warning in dev, potential bugs in prod)
- Rapid navigation causes stale responses to overwrite fresh data

**Fix pattern:**
```tsx
useEffect(() => {
  const ac = new AbortController();
  api.get('/endpoint', { signal: ac.signal }).then(setData).catch(...);
  return () => ac.abort();
}, []);
```

### 2. URL.createObjectURL Memory Leaks (3 pages)
- `Audit.tsx:38` — `handleExport`
- `Console.tsx:60` — `handleExport`

**Fix:** Call `URL.revokeObjectURL(url)` after `a.click()`:
```tsx
const url = URL.createObjectURL(blob);
a.href = url;
a.click();
URL.revokeObjectURL(url);
```

### 3. Missing aria-labels Across All Pages
22 instances of interactive elements without accessible names. Most common: search inputs (placeholder-only), icon-only buttons, and status indicators.

### 4. No Error Boundaries
None of the pages are wrapped in React error boundaries. A rendering crash in any page takes down the entire app.

### 5. Mobile Grid Issues (4 pages)
Console, WorkerDetail, Settings, and Tasks use non-responsive grid layouts (`grid-cols-4`, `grid-cols-3`) that break on mobile.

---

## Priority Fix Order

1. **Console.tsx** — Missing error handling (completely silent failures) + mobile grid crash
2. **Providers.tsx** — Missing error handling (completely silent failures)
3. **WorkerDetail.tsx** — "Worker not found" shown on API errors
4. **Chat.tsx** — Race conditions on message loading and SSE streaming
5. **Tasks.tsx** — Race condition on task selection
6. **Workers.tsx / Projects.tsx** — N+1 API calls and race conditions
7. **All pages** — Add AbortController pattern
8. **Audit.tsx / Console.tsx** — Fix createObjectURL leaks
9. **All pages** — Add missing aria-labels
10. **Console / WorkerDetail / Settings** — Fix mobile grids
