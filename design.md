# Design — Before You Buy

Locked design system for the storefront (`frontend/`). Written with the Hallmark skill
(`.claude/skills/hallmark`, installed for this project only). Pages extend this file; they do not
re-pick a theme.

## Genre
Editorial. A furniture shop that sells on measured fact, so the page reads like a catalogue with
a ruler in it: serif display, quiet paper, one amber accent, numbered sections.

## Macrostructure family
- Marketing (`/store`): split hero (copy left, drawn floor plan right) → numbered sections.
- App (`/room-simulator`, `/workspace`, `/product/[sku]`): function carries the page; no enrichment.

## Theme (tokens live in `frontend/src/app/globals.css`)
- Paper / ink: warm neutrals, hue ~60–85, chroma ≤ 0.02. Light and dark are both first-class.
- One accent: amber (`--primary`), kept under ~5 % of a viewport.
- Verdict colours (`--success`, `--warning`, `--destructive`) are for verdicts only.
- No gradient backgrounds on heroes, no glow blobs.

## Typography
- Display: Fraunces, roman only (never italic), weight 500, tracking −0.02em — headings and the wordmark.
- Body: Geist. Mono: Geist Mono, reserved for what a person copies (SKU, URL, tool name).
- Labels: `eyebrow` utility (small caps-style, wide tracking).

## Spacing
Multiples of 4. Section rhythm: 64 / 96 px vertical.

## Motion
Ease-out only, ≤ 200 ms for UI; reduced-motion collapses everything (see globals.css).

## CTA voice
- Primary: solid ink fill, full pill radius, no icon.
- Secondary: outline, same shape.

## Honest copy
No invented numbers. Every verdict shown is the geometry engine's; illustrations say they are illustrations.

## What pages MUST share
Wordmark in Fraunces, accent placement, `01 / Label` section heading pattern, CTA voice.
