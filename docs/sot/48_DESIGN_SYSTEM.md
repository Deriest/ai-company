# 48 — Design System

**Release Scope:** v2.0.2 → v2.1.0
**Status:** Source of Truth (Implementation Contract)

---

## Visual Identity

### Color Tokens (Deep Void Theme)

| Token | Value | Usage |
|---|---|---|
| `--bg-base` | `#0a0e14` | Root background |
| `--bg-surface` | `#111722` | Card, sidebar, panel backgrounds |
| `--bg-surface-active` | `#1a2233` | Hover, selected states |
| `--bg-overlay` | `#0d1117` | Modal, dropdown backgrounds |
| `--border-base` | `#1e2a3a` | Default borders |
| `--border-strong` | `#2a3a4e` | Emphasized borders |
| `--accent-primary` | `#38bdf8` | Primary actions, links, active states |
| `--accent-secondary` | `#818cf8` | Secondary emphasis |
| `--text-0` | `#e6edf3` | Primary text |
| `--text-1` | `#c9d1d9` | Body text |
| `--text-2` | `#8b949e` | Secondary text |
| `--text-3` | `#484f58` | Muted text, labels |
| `--status-success` | `#3fb950` | Success states |
| `--status-error` | `#f85149` | Error states |
| `--status-warning` | `#d29922` | Warning states |

### Typography

| Element | Font | Size | Weight | Usage |
|---|---|---|---|---|
| Page title | Inter | 20px | 600 | Mission names, view headers |
| Section heading | Inter | 16px | 600 | Card titles, section headers |
| Body text | Inter | 13px | 400 | Default body, descriptions |
| Small/label | Inter | 11px | 500 | Badges, labels, uppercase section headers |
| Code/mono | Fira Code | 12px | 400 | File paths, commands, technical data |

### Spacing System (8px base)

| Token | Value | Usage |
|---|---|---|
| `--space-xs` | 4px | Tight gaps (icon to label) |
| `--space-sm` | 8px | Default gap within components |
| `--space-md` | 12px | Component padding |
| `--space-lg` | 16px | Section gaps |
| `--space-xl` | 24px | View padding |
| `--space-2xl` | 32px | Major section separation |

### Border Radius

| Token | Value | Usage |
|---|---|---|
| `--radius-sm` | 4px | Badges, tags, small elements |
| `--radius-md` | 6px | Cards, inputs, buttons |
| `--radius-lg` | 8px | Modals, panels |

## Component Standards

### Buttons

| Type | Appearance | Usage |
|---|---|---|
| `.primary` | Filled accent bg, white text | Primary action (one per view) |
| `.secondary` | Ghost with border | Secondary actions |
| `.danger.secondary` | Ghost with red border | Destructive actions (cancel, delete) |
| `.icon-btn` | Icon-only, no border | Toolbar actions (close, toggle) |
| `.ghost` | Text-only, no visual weight | Inline actions, links |

### Cards

| Type | Usage |
|---|---|
| `.card-elevated` | Surface bg + border + shadow | Content cards, mission details |
| `.card-flat` | Surface bg + no shadow | Inline information blocks |

### Badges

| Type | Usage |
|---|---|
| `.badge` | Neutral info (model name, version) |
| `.badge.success` | Connected, completed |
| `.badge.error` | Offline, failed |
| `.badge.accent` | Active provider, update ready |

### Inputs

| Type | Usage |
|---|---|
| `input[type=text]` | Dark bg, mono font for technical inputs |
| `textarea` | Multi-line descriptions |
| `select` | Dropdowns (styled via form-dark.css) |

### Tables

| Element | Style |
|---|---|
| Header | Uppercase 11px, muted text, border-bottom |
| Row | Hover highlight, pointer cursor |
| Cell | 13px body text, mono for IDs/paths |

## CSS Files

| File | Purpose |
|---|---|
| `styles/global.css` | Design tokens, layout, all component styles |
| `styles/form-dark.css` | Form element overrides for dark theme |

### Issues

1. **Google Fonts imported via CDN** (`Inter`, `Fira Code`) — creates external network dependency in offline desktop app. Must bundle fonts or use system fallbacks.
2. **Inline styles dominate** — many components use `style={{}}` instead of CSS classes. Must migrate to token-based classes.
3. **No CSS custom property for font stack** — hardcoded `Inter, system-ui` in multiple places.
4. **Fixed sidebar/panel widths** — 300px sidebar, 250px panel. Should be resizable.
