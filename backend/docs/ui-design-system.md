# AIC Platform — UI Design System

**Version:** 1.0.0  
**Date:** 2026-07-22  
**Status:** Production Ready

## Overview

Complete redesign of AIC Platform UI from generic Tailwind utilities to a cohesive, futuristic AI Operating System aesthetic. The design system provides a consistent visual language across all 13 application pages.

---

## Design Philosophy

### Core Principles

1. **Futuristic AI-Native** — Feels like operating an autonomous AI company, not a traditional web app
2. **Glass Morphism** — Layered, translucent surfaces with backdrop blur
3. **Neural Aesthetics** — Gradients inspired by neural networks (indigo → purple → pink)
4. **High Information Density** — Maximum useful data without visual clutter
5. **Real-time Feel** — Live metrics, streaming indicators, pulsing status badges

### NOT This

- ❌ Bootstrap admin panel
- ❌ Generic CRUD dashboard
- ❌ Template marketplace clone
- ❌ Tailwind component library demo

### YES This

- ✅ ChatGPT-level polish
- ✅ Linear's spatial hierarchy
- ✅ Arc Browser's premium feel
- ✅ Vercel Dashboard's clarity
- ✅ Cursor's engineering focus

---

## Color System

### Base Palette

```typescript
colors: {
  bg: {
    primary: '#0a0e1a',      // Deep space background
    secondary: '#0f1623',    // Card/panel background
    tertiary: '#151b2e',     // Elevated surfaces
  },
  
  glass: {
    light: 'rgba(255, 255, 255, 0.03)',
    medium: 'rgba(255, 255, 255, 0.05)',
    strong: 'rgba(255, 255, 255, 0.08)',
  },
}
```

### Brand Gradients

```css
/* Primary */
from-indigo-500 to-purple-600

/* Neural (multi-stop) */
from-indigo-500 via-pink-500 to-purple-600

/* Status */
from-emerald-500 to-emerald-600  /* Success */
from-amber-500 to-amber-600      /* Warning */
from-red-500 to-red-600          /* Error */
```

### Text Hierarchy

- **Primary:** `#f1f5f9` — Headlines, primary content
- **Secondary:** `#cbd5e1` — Body text
- **Tertiary:** `#64748b` — Captions, labels
- **Muted:** `#475569` — Disabled, placeholders
- **Disabled:** `#334155` — Inactive elements

---

## Typography

### Font System

```typescript
fontFamily: {
  sans: 'ui-sans-serif, system-ui, -apple-system, "Segoe UI", Roboto',
  mono: 'ui-monospace, "JetBrains Mono", "Fira Code", Consolas',
}

fontSize: {
  xs: '11px',    // Labels, badges
  sm: '13px',    // Body text, UI
  base: '15px',  // Default
  lg: '17px',    // Subheadings
  xl: '20px',    // Section titles
  '2xl': '24px', // Page headers
  '3xl': '30px', // Hero text
}
```

### Font Weight

- **Normal:** 400 — Body text
- **Medium:** 500 — UI elements
- **Semibold:** 600 — Headings
- **Bold:** 700 — Emphasis

---

## Spacing & Layout

### Grid System

- **4px base unit** — All spacing uses multiples of 4
- **Responsive breakpoints:**
  - Mobile: `< 768px`
  - Tablet: `768px - 1024px`
  - Desktop: `> 1024px`
  - Wide: `> 1600px`

### Container Max-Widths

```typescript
Dashboard: 1600px
Forms: 800px
Content: 1200px
Chat: Full width
```

---

## Components

### Surface

Base container with glass morphism and elevation variants.

```tsx
<Surface 
  variant="default"    // default | elevated | inset
  glass={true}         // Enable backdrop blur
  glow={false}         // Add colored shadow
  hover={true}         // Interactive states
  onClick={() => {}}   // Click handler
>
  {children}
</Surface>
```

**Variants:**

- `default` — Standard card (bg-[#0f1623])
- `elevated` — Raised surface with shadow
- `inset` — Depressed surface (bg-[#0a0e1a])

### Button

```tsx
<Button
  variant="primary"    // default | primary | success | danger | ghost
  size="md"           // sm | md | lg
  loading={false}     // Show spinner
  leftIcon={<Icon />}
  rightIcon={<Icon />}
>
  Label
</Button>
```

**Visual States:**

- Primary: Indigo-purple gradient + glow
- Success: Emerald gradient + glow
- Danger: Red gradient + glow
- Ghost: Transparent, hover fill
- Default: Subtle glass surface

### Badge

```tsx
<Badge
  variant="info"      // default | primary | success | warning | error | info
  size="sm"          // sm | md
  dot={true}         // Status indicator
  pulse={false}      // Animated pulse
>
  Label
</Badge>
```

### Input

```tsx
<Input
  label="Field Label"
  error="Validation message"
  leftIcon={<Icon />}
  rightIcon={<Icon />}
  placeholder="Enter value..."
/>
```

**States:**

- Default: Glass background
- Focus: Indigo ring
- Error: Red border + ring
- Disabled: Reduced opacity

### Typography Components

```tsx
<Heading level={1}>Page Title</Heading>
<Text variant="sm" color="tertiary" weight="medium">
  Body text
</Text>
```

---

## Layout Patterns

### Application Shell

```
┌─────────────────────────────────────────┐
│  Sidebar (240px)    │   Main Content    │
│  ┌──────────────┐   │  ┌──────────────┐ │
│  │ Brand        │   │  │ Page Header  │ │
│  ├──────────────┤   │  ├──────────────┤ │
│  │ Navigation   │   │  │              │ │
│  │              │   │  │   Content    │ │
│  │              │   │  │   Area       │ │
│  │              │   │  │              │ │
│  ├──────────────┤   │  │              │ │
│  │ Provider     │   │  │              │ │
│  │ User Info    │   │  │              │ │
│  └──────────────┘   │  └──────────────┘ │
└─────────────────────────────────────────┘
```

### Page Structure

```tsx
<div className="flex-1 overflow-y-auto">
  <div className="p-6 lg:p-8 space-y-8 max-w-[1600px] mx-auto">
    {/* Header */}
    <div>
      <Heading level={1}>Page Title</Heading>
      <Text variant="sm" color="tertiary">Description</Text>
    </div>
    
    {/* Content */}
    <Surface>{/* ... */}</Surface>
  </div>
</div>
```

---

## Phase & Status Visualization

### Task Phases

```typescript
const PHASES = [
  'created',
  'investigate',
  'planning',
  'implementation',
  'verification',
  'closeout',
  'completed',
  'failed',
  'blocked',
  'cancelled',
]
```

**Color Mapping:**

- Created: Slate (neutral)
- Investigate: Blue (info)
- Planning: Purple (primary)
- Implementation: Amber (warning/active)
- Verification: Cyan (info)
- Closeout: Purple (primary)
- Completed: Emerald (success)
- Failed/Blocked: Red (error)
- Cancelled: Gray (disabled)

### Phase Progress

```tsx
<PhaseProgress phase="implementation" progress={45} />
```

Visual: Gradient progress bar + phase badge + percentage

### Worker Status

```tsx
<WorkerStatusBadge status="working" />
```

- Idle: Gray
- Working: Emerald + pulse animation
- Error: Red
- Offline: Dark gray

---

## Animation & Motion

### Timing Functions

```typescript
transition: {
  fast: '150ms cubic-bezier(0.4, 0, 0.2, 1)',
  normal: '250ms cubic-bezier(0.4, 0, 0.2, 1)',
  slow: '350ms cubic-bezier(0.4, 0, 0.2, 1)',
  spring: '400ms cubic-bezier(0.34, 1.56, 0.64, 1)',
}
```

### Animation Patterns

**Pulse (Status Indicators):**
```css
animate-pulse  /* Working status, active workers */
```

**Glow (Active Elements):**
```css
shadow-[0_0_20px_rgba(99,102,241,0.3)]
```

**Hover States:**
```css
hover:border-white/[0.16] 
hover:shadow-xl 
transition-all duration-200
```

**Floating Orbs (Login Background):**
```css
.orbs-bg::before { animation: float 20s ease-in-out infinite; }
```

---

## Responsive Behavior

### Sidebar

- **Desktop:** Always visible, 240px fixed
- **Tablet:** Collapsible, overlay on open
- **Mobile:** Hidden by default, hamburger menu

### Grid Layouts

```tsx
// Workers, Projects, Stats
<div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-4">
```

### Chat Interface

- **Desktop:** Sidebar + main (split layout)
- **Mobile:** Full-screen messages, sidebar overlay

---

## Accessibility

### Keyboard Navigation

- Tab order follows visual hierarchy
- Focus visible with indigo ring
- Escape closes modals/overlays

### ARIA Labels

```tsx
<button aria-label="Refresh dashboard">
  <RefreshIcon />
</button>
```

### Color Contrast

- All text meets WCAG AA minimum (4.5:1)
- Interactive elements have hover/focus states
- Status colors are badge-backed (not color-only)

---

## Dark Theme Only

The design system is **dark theme first** with no light mode support. Reasons:

1. AI/terminal aesthetic
2. Reduced eye strain for long sessions
3. Better for data-dense interfaces
4. Matches developer tool conventions

Background: Deep space navy (`#0a0e1a`), not pure black.

---

## Icon System

**Library:** Heroicons v2 (outline, 1.5px stroke)

**Usage:**
```tsx
import { TaskIcon, WorkerIcon } from '../design-system/icons';
```

**Size Convention:**
- Small: `w-4 h-4` (16px)
- Medium: `w-5 h-5` (20px)
- Large: `w-6 h-6` (24px)

---

## Page-Specific Patterns

### Dashboard

- 7-stat grid with gradient cards
- Live event stream with severity badges
- Auto-refresh every 30s

### Chat

- ChatGPT-style message bubbles
- Streaming response with typing indicator
- Markdown rendering with syntax highlighting
- Token usage metadata per message

### Tasks

- Phase-aware progress visualization
- Dispatch button for created tasks
- Expandable context on click
- Status-colored badges

### Workers

- Live status with pulse animation
- Capability badges
- Active lease counter
- Click to detail view

---

## Implementation Notes

### File Structure

```
frontend/src/
├── design-system/
│   ├── tokens.ts        # Color, spacing, typography
│   ├── components.tsx   # UI primitives
│   ├── icons.tsx        # Icon components
│   ├── utils.tsx        # Phase badges, time formatting
│   └── index.ts         # Public API
├── pages/               # 13 application pages
├── components/
│   └── Layout.tsx       # App shell
└── index.css            # Global styles, animations
```

### Import Pattern

```tsx
import {
  Surface,
  Button,
  Badge,
  Heading,
  Text,
} from '../design-system';
```

### Tailwind 4 Integration

Uses `@import "tailwindcss"` with custom theme tokens in `index.css`.

---

## Performance

### Bundle Size

- CSS: 57KB (gzipped: 9.5KB)
- JS: 311KB (gzipped: 91KB)
- Total: ~100KB gzipped

### Optimization Strategies

1. Tree-shaking via ES modules
2. No external icon libraries (inline SVGs)
3. CSS-only animations (no JS libraries)
4. Lazy-loaded routes (future)

---

## Future Enhancements

### Phase 2 Considerations

- [ ] Data visualization library (charts)
- [ ] Advanced markdown (tables, footnotes)
- [ ] Virtual scrolling for large lists
- [ ] WebSocket live updates
- [ ] Keyboard shortcuts
- [ ] Command palette (⌘K)
- [ ] Theme customization UI
- [ ] Motion preferences (reduce-motion)

---

## Migration Guide

### From Old UI

**Before:**
```tsx
<Card hover>
  <StatusBadge status={status} />
  <div className="text-sm text-slate-500">Label</div>
</Card>
```

**After:**
```tsx
<Surface hover onClick={handleClick}>
  <Badge variant="info" dot pulse>{status}</Badge>
  <Text variant="sm" color="tertiary">Label</Text>
</Surface>
```

### Key Changes

1. `Card` → `Surface` (with variants)
2. Tailwind classes → Design system components
3. Custom colors → Token-based palette
4. Inline styles → Component props
5. Bootstrap-style → Glass morphism

---

## References

### Inspiration

- **ChatGPT** — Chat UX, message layout
- **Linear** — Status badges, keyboard nav
- **Vercel Dashboard** — Card design, spacing
- **Arc Browser** — Glass effects, gradients
- **Cursor** — Code blocks, terminal feel

### Resources

- Design tokens: `/frontend/src/design-system/tokens.ts`
- Component library: `/frontend/src/design-system/components.tsx`
- Usage examples: All pages in `/frontend/src/pages/`

---

**Last Updated:** 2026-07-22  
**Maintained By:** AIC Platform Team
