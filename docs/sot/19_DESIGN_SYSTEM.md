# 19 — Design System

**Subsystem:** Design Tokens, Typography & Component Standards  

---

## 1. Design Tokens

```css
:root {
  --void: #05060a;
  --surface-0: #0a0c12;
  --surface-1: #10141c;
  --surface-2: #161c28;
  --line: rgba(255, 255, 255, 0.08);
  --line-strong: rgba(255, 255, 255, 0.14);
  --text-1: #e8ecf4;
  --text-2: #9aa3b5;
  --text-3: #5c6578;
  --accent: #3ddc97;
  --accent-2: #5b8cff;
  --warn: #f0b429;
  --danger: #f07178;
  --idle: #3a4150;
  --font-ui: "IBM Plex Sans", system-ui, sans-serif;
  --font-mono: "IBM Plex Mono", monospace;
  --radius: 6px;
}
```

## 2. Component Design Guidelines

- **Cards (`.card-elevated`):** Subtle 1px lines (`var(--line)`), rounded 6px borders, dark surface background.
- **Buttons:** `primary` (accent gradient), `ghost` (transparent background), explicit focus rings.
- **Inputs & Selects:** Dark background (`var(--surface-0)`), no default browser white outlines.
