# 18 — UI Constitution

**Subsystem:** Desktop Frontend Architecture
**Framework:** React 19, Tailwind v4, Vite 6, Electron 39
**Version:** v2.3.0

---

## 1. Principles of Interface Design

1. **Engineering-First:** The UI is an engineering workspace, not a marketing page. Data density, typography, and contrast must prioritize readability.
2. **Dark-First Theme:** Uses high-contrast dark palette with OKLCH color space. Primary colors: cyan/teal (`oklch(0.78 0.13 195)`), success green, warning amber, destructive red.
3. **No Synthetic or Placeholder UI:** All data reflects real backend state. Fake progress bars and synthetic placeholder strings are prohibited.
4. **Keyboard-First Navigation:** Global shortcuts for all primary actions.

---

## 2. Navigation Structure

```
Sidebar (always visible):
  🏠 Office           — Live Office Floor (animated 2D visualization)
  ❯ Command Center    — OpenCode-style chat with tool panels
  👥 Live Company      — Org chart (15 workers × 4 departments) + token cost
  🔧 Skills            — Skill registry management
  🔌 MCP Servers       — MCP server management
  ⚙️ Settings          — General | Providers | Auto Approve
```

**Active state:** Current view highlighted with accent color. Subtle hover states on inactive items.

---

## 3. Layout Shell

```
┌─────────────────────────────────────────────┐
│ Header (36px): Logo + title + window controls│
├────────┬────────────────────────────────────┤
│Sidebar │                                    │
│(224px) │  Main Content Area                 │
│        │  (scrollable, flex-1)              │
│ Nav    │                                    │
│ items  │                                    │
│        │                                    │
│ User   │                                    │
│ profile│                                    │
├────────┴────────────────────────────────────┤
│ Footer (28px): Status + model + version      │
└─────────────────────────────────────────────┘
```

---

## 4. Design Tokens

| Token | Value | Usage |
|-------|-------|-------|
| `--background` | `oklch(0.15 0.015 250)` | Page background |
| `--card` | `oklch(0.18 0.015 250)` | Card/panel background |
| `--border` | `oklch(0.25 0.01 250)` | Borders |
| `--primary` | `oklch(0.78 0.13 195)` | Primary accent (cyan) |
| `--success` | `oklch(0.72 0.16 155)` | Success states |
| `--warning` | `oklch(0.78 0.15 75)` | Warning states |
| `--destructive` | `oklch(0.62 0.2 18)` | Error/destructive |
| `--foreground` | `oklch(0.95 0.01 250)` | Primary text |
| `--muted` | `oklch(0.5 0.02 250)` | Secondary text |

**Typography:** Inter (sans) + Fira Code (monospace)

---

## 5. Component Library

| Component | Usage |
|-----------|-------|
| `PageHeader` | Page title + subtitle + actions |
| `Card` | Content container with border |
| `Badge` | Status/tier indicators |
| `ProgressBar` | Task progress |
| `Avatar` | User/worker initials |

---

## 6. Keyboard Shortcuts

| Shortcut | Action |
|----------|--------|
| `Ctrl+K` | Command Palette |
| `Ctrl+1` | Office view |
| `Ctrl+2` | Command Center |
| `Ctrl+3` | Live Company |
| `Ctrl+4` | Skills |
| `Ctrl+5` | MCP Servers |
| `Ctrl+6` | Settings |
| `Ctrl+N` | New session |
| `Ctrl+`` ` | Toggle terminal |
| `Enter` | Send message |
| `Shift+Enter` | Newline in composer |

---

## 7. Anti-Patterns (DILANGGAR)

- ❌ Chat bubbles with avatars (use terminal-style messages instead)
- ❌ Placeholder "Coming soon" views
- ❌ Hardcoded data in components
- ❌ Raw Tailwind colors (must use design tokens)
- ❌ Native HTML form elements (must use styled components)
- ❌ Loading spinners for instant operations
