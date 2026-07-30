# Design Decisions

## 1. Public first, operations second
**Decision:** `/` is a public product experience. Authenticated dashboard moves to `/app`.

**Why:** The mission requires a cinematic arrival and product explanation. Opening directly into login or a dashboard makes AIC feel like an internal admin tool, not a product.

## 2. No new frontend dependency
**Decision:** Keep React, React Router, Tailwind, and the existing design-system primitives. Do not add Three.js, Framer Motion, chart libraries, or icon packs.

**Why:** The current package set is already production-capable. CSS can deliver the first viewport identity without GPU risk, install friction, or bundle inflation. Three.js remains an upgrade path if a later visual requires true 3D interaction.

## 3. CSS-only “AI core” instead of WebGL
**Decision:** Represent the live AI core with orbits, nodes, grid, and pulse built from CSS.

**Why:** The first viewport must feel alive without becoming a performance liability. A CSS core is enough to communicate system energy and remains compatible with reduced motion.

## 4. Graphite instrumentation, not neon carnival
**Decision:** Use graphite backgrounds, cyan command accents, violet AI energy, and sparse green health indicators.

**Why:** Excessive neon and multi-gradient surfaces read as template cyberpunk. Instrument-panel restraint better matches a commercial operating system.

## 5. Editorial hierarchy over card spam
**Decision:** Public sections use large typography, section rules, and sparse cards. Cards are not the default layout primitive.

**Why:** Premium product pages (Linear, Stripe, Vercel) communicate hierarchy with type and spacing, not dense SaaS card grids.

## 6. Preserve authenticated API contracts
**Decision:** Redesign identity and navigation without changing backend contracts or inventing new operational pages.

**Why:** The product is already functional. The redesign must raise the experience without breaking the operating surface.

## 7. Login is part of the product narrative
**Decision:** Login is a command-entry surface, not a floating SaaS card over animated orbs.

**Why:** Authentication is the threshold between public product story and private command floor. It should continue the same visual and informational language.

## 8. Reduced motion is mandatory
**Decision:** Global reduced-motion support disables non-essential animation.

**Why:** Motion is identity, not content. Accessibility and comfort take priority over spectacle.

## Trade-offs accepted
- No interactive 3D or particle engine yet.
- Authenticated pages reuse the existing design-system shell rather than being fully rewritten page-by-page in one pass.
- Visual browser screenshots could not be captured in this environment because the browser daemon timed out.
