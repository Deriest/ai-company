# AIC Platform Visual Language Extraction

## From aic-skill/dashboard Reference

### Core Identity
**Pixel Dashboard / Cyber Control Room**

### Typography
- Primary: Press Start 2P (pixel font)
- Pixel-perfect rendering for retro-tech feel

### Color System (from tailwind config analysis needed)
- Background: Deep dark (`#0a0a1a`)
- Panel BG: Dark navy
- Border: Technical blue
- Accent: Electric cyan (`#00d4ff`)
- Secondary: Neon green (`#00ff88`)
- Text: Light gray/white

### Visual Treatments
1. **CRT Scanlines** — Fixed overlay with repeating 2px gradient (rgba(0,0,0,0.15))
2. **Top border accent** — 3px cyan stripe (`#00d4ff`) on panels
3. **Office grid** — 20px grid pattern overlay (rgba(42,42,74,0.1))
4. **Text glow** — Cyan and green text-shadow for accent elements
5. **Pixel hover** — scale-105 transform on interactive elements
6. **Border thickness** — 3px solid borders (not 1px)
7. **Scroll shadows** — Gradient fade on scroll containers

### Spacing & Layout
- Dense operational layout
- Grid-based positioning
- Pixel-aligned elements
- 20px grid system

### Component Patterns
- `.panel` class with top cyan border
- `.office-grid-bg` with grid overlay
- `.pixel-desk` hover treatment
- `.text-glow-accent` and `.text-glow-green` utilities

### Motion
- `transition-transform duration-200`
- Hover scale effects
- Minimal animation (retro constraint)

### Technical Details
- Fixed body height, overflow hidden
- Custom 6px scrollbar with dark theme
- Pointer-events:none on overlays (scanlines)
- Z-index layering (scanline=50)

---

## Design System to Build for AIC Platform

Based on aic-skill reference + modern premium futuristic requirements:

**Color Palette:**
- Deep space black: `#07090e` (current) → keep
- Panel dark: `#0d121b`
- Border: Electric cyan `#00d4ff` (from aic-skill)
- Accent primary: Cyan `#22d3ee`
- Accent secondary: Violet/purple `#a78bfa`
- Success: Neon green `#10b981`
- Warning: Amber `#f59e0b`
- Error: Red `#ef4444`

**Typography:**
- Headers: Tight tracking, bold weight
- Body: 15px readable sans-serif
- Monospace: For code/data
- Optional pixel font for specific UI elements (not everything)

**Visual Elements:**
- Scanline overlay (subtle)
- Grid background (20px)
- 3px borders where appropriate
- Cyan top stripe on panels
- Text glow on accent elements
- Smooth transitions
- Depth via layering

**Components:**
- Dark panels with cyan accent borders
- Glow effects on interactive elements
- Pixel-inspired but not 8-bit everywhere
- Dense information layout
- Technical dashboard aesthetic

**3D/Motion:**
- Animated hero scene (CSS or lightweight Three.js)
- Particle field background
- Smooth page transitions
- Hover glow effects
- Live pulsing status indicators

Next: Apply this to build landing page first.
