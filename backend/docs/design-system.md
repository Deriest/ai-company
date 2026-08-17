# AIC Platform Design System

## Philosophy
AIC is presented as an AI Company Operating System: calm mission control for autonomous work, not a generic admin panel. The visual language uses engineering instrumentation, restrained neon, deep graphite surfaces, and explicit operational states.

## Tokens

| Token | Value | Use |
|---|---|---|
| `ink` | `#edf2f7` | Primary text |
| `muted` | `#8a94a6` | Secondary copy |
| `line` | `rgba(150,170,200,.16)` | Structural borders |
| `cyan` | `#78e7ef` | Active command, focus, live state |
| `violet` | `#a88cff` | AI core and secondary system energy |
| `green` | `#72edc8` | Healthy/online state |
| `graphite` | `#07090e` | Global background |

## Typography
- UI and reading copy use the system sans stack for fast rendering and platform familiarity.
- Instrumentation, labels, IDs, and status values use a monospace stack.
- Display headings use tight tracking and short line lengths to create an editorial command-center hierarchy.
- Letter spacing is never scaled with viewport width.

## Spacing and Shape
- Landing layout uses a 1280px reading canvas with 24-40px responsive gutters.
- Structural sections use 1px rules instead of card stacks.
- Cards are reserved for repeated feature/workforce items and operational surfaces.
- Public CTA buttons use a rectangular command affordance; ordinary app controls retain existing component primitives.

## Motion
- The core uses low-frequency orbit, drift, and pulse motion to communicate a live system.
- Worker states use a restrained status blink.
- `prefers-reduced-motion: reduce` disables non-essential animation and transitions.
- Motion is decorative on the landing page and must never be required to understand content.

## Components and Patterns
- `Landing`: public arrival, product explanation, workforce, architecture, and conversion path.
- `Core`: CSS-only live AI core; no new runtime dependency or WebGL cost.
- `phase-card`: visible governed lifecycle.
- `worker-row`: operational roster with role and status.
- `architecture-map`: lightweight system relationship visual.
- Existing app primitives in `frontend/src/design-system/` remain the source of truth for authenticated surfaces.

## Accessibility
- Semantic sections, headings, nav labels, `main`, `footer`, and list roles are used.
- Skip link and visible focus rings are present.
- Decorative visuals have `aria-hidden`; the core and architecture visual expose concise labels.
- Public actions use real links for navigation.
- Reduced motion is supported globally.

## Performance
- No new dependency was added.
- The public 3D-like visuals are CSS-only, avoiding GPU-heavy WebGL for the first viewport.
- Production build output after the redesign: 94.08 KB JS gzip and 12.98 KB CSS gzip.

## Naming Convention
- Public page styles use `landing-*`, `hero-*`, `core-*`, `phase-*`, `worker-*`, and `map-*` prefixes.
- Authenticated product styles continue using existing design-system primitives and utility classes.
