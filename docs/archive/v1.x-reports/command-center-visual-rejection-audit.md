# Command Center Visual Rejection Audit

This document notes the visual failures of the current Command Center dashboard implementation compared to the accepted premium pixel-tech design system of AIC Platform.

## Visual Weaknesses & Failures Identified
1. **Sidebar is generic**: Simple plain text and basic icons. Weak active state indicators, lacks a dedicated, styled Command Rail identity with collapsing functionality, tooltips, and real-time active provider/thinker state.
2. **Top Bar wastes horizontal space**: Only has breadcrumbs on the left and a tiny clock on the right. Lacks functional items like a search/command trigger, status badges (running tasks, approvals), and a proper glass/depth layout.
3. **Header is plain**: "Command Center - Autonomous engineering operations at a glance" feels like a generic template. It needs a high-fidelity operational layout with active states, last sync timer, and premium headers.
4. **Metric cards are rectangles**: Simple grid of standard cards with top borders. Wastes space and lacks telemetry dense labels, micro-sparklines, technical borders, status pulses, or custom pixel-art borders.
5. **AI Company Network is NOT a network**: Displays columns of workers next to a dispatcher node. Completely misses the interactive node-topology requirement.
6. **System Health wastes space**: Extremely tall layout for only 4-5 list items. Needs to be a high-density compact status panel.
7. **Active Operations lacks operational details**: Basic HTML rows without progress badges, elapsed timers, worker tier indicator, or drawer interactions.
8. **Attention Center lacks layout hierarchy**: Standard list items with little prominence. Should act as a clean, high-priority dashboard gate.
9. **No Token Flow graph**: Simple token number metric without visual area/line charts, inputs, outputs, or cache status.
10. **Flat Visual Depth**: Lacks grids, radial glows, terminal textures, scanlines, or depth markers. Flat colors do not align with the premium glassmorphism landing page.

## Remediation Plan
- Rebuild layout in `Dashboard.tsx` with high-density sections.
- Re-architect `AppShell.tsx` to integrate the AIC Command Rail with collapsible states and active provider diagnostics.
- Build custom SVG/Canvas/CSS Topology in `Dashboard.tsx` displaying the Dispatcher core surrounded by worker nodes with state-aware connection paths.
- Enrich CSS rules in `components.css` to add glowing grids, scanlines, pixel-tech borders, status pulses, and glassmorphic layers.
- Implement responsive viewport optimizations down to mobile (390px).
