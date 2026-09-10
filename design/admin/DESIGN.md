---
name: Rochade
colors:
  surface: '#0f131c'
  surface-dim: '#0f131c'
  surface-bright: '#353942'
  surface-container-lowest: '#0a0e16'
  surface-container-low: '#181c24'
  surface-container: '#1c2028'
  surface-container-high: '#262a33'
  surface-container-highest: '#31353e'
  on-surface: '#dfe2ee'
  on-surface-variant: '#c6c6cd'
  inverse-surface: '#dfe2ee'
  inverse-on-surface: '#2c3039'
  outline: '#909097'
  outline-variant: '#45464d'
  surface-tint: '#bec6e0'
  primary: '#bec6e0'
  on-primary: '#283044'
  primary-container: '#0f172a'
  on-primary-container: '#798098'
  inverse-primary: '#565e74'
  secondary: '#b4c5ff'
  on-secondary: '#002a78'
  secondary-container: '#0053db'
  on-secondary-container: '#cdd7ff'
  tertiary: '#dec29a'
  on-tertiary: '#3e2d11'
  tertiary-container: '#231500'
  on-tertiary-container: '#957d5a'
  error: '#ffb4ab'
  on-error: '#690005'
  error-container: '#93000a'
  on-error-container: '#ffdad6'
  primary-fixed: '#dae2fd'
  primary-fixed-dim: '#bec6e0'
  on-primary-fixed: '#131b2e'
  on-primary-fixed-variant: '#3f465c'
  secondary-fixed: '#dbe1ff'
  secondary-fixed-dim: '#b4c5ff'
  on-secondary-fixed: '#00174b'
  on-secondary-fixed-variant: '#003ea8'
  tertiary-fixed: '#fcdeb5'
  tertiary-fixed-dim: '#dec29a'
  on-tertiary-fixed: '#271901'
  on-tertiary-fixed-variant: '#574425'
  background: '#0f131c'
  on-background: '#dfe2ee'
  surface-variant: '#31353e'
  surface-hall-bg: '#0B0F17'
  surface-hall-card: '#131B2A'
  surface-hall-card-hover: '#1E293B'
  surface-admin-bg: '#F8FAFC'
  surface-admin-card: '#FFFFFF'
  surface-admin-subtle: '#F1F5F9'
  border-dark: '#1E293B'
  border-dark-strong: '#334155'
  border-light: '#E2E8F0'
  border-light-strong: '#CBD5E1'
  text-dark-primary: '#F8FAFC'
  text-dark-secondary: '#94A3B8'
  text-dark-muted: '#64748B'
  text-light-primary: '#0F172A'
  text-light-secondary: '#475569'
  text-light-muted: '#94A3B8'
  status-empty: '#64748B'
  status-empty-bg: '#1E293B'
  status-claimed: '#F59E0B'
  status-claimed-bg: '#78350F'
  status-disputed: '#E11D48'
  status-disputed-bg: '#4C0519'
  status-confirmed: '#059669'
  status-confirmed-bg: '#064E3B'
  round-open: '#2563EB'
  round-released: '#D97706'
  round-exported: '#64748B'
  disc-white-fill: '#FFFFFF'
  disc-white-stroke: '#94A3B8'
  disc-black-fill: '#0F172A'
  disc-black-stroke: '#475569'
typography:
  display-hero:
    fontFamily: Geist
    fontSize: 48px
    fontWeight: '700'
    lineHeight: 52px
    letterSpacing: -0.03em
  headline-lg:
    fontFamily: Geist
    fontSize: 32px
    fontWeight: '600'
    lineHeight: 38px
    letterSpacing: -0.02em
  headline-lg-mobile:
    fontFamily: Geist
    fontSize: 26px
    fontWeight: '600'
    lineHeight: 32px
    letterSpacing: -0.02em
  headline-md:
    fontFamily: Geist
    fontSize: 22px
    fontWeight: '600'
    lineHeight: 28px
    letterSpacing: -0.015em
  headline-sm:
    fontFamily: Geist
    fontSize: 18px
    fontWeight: '600'
    lineHeight: 24px
    letterSpacing: -0.01em
  body-lg:
    fontFamily: Geist
    fontSize: 17px
    fontWeight: '400'
    lineHeight: 24px
    letterSpacing: -0.005em
  body-md:
    fontFamily: Geist
    fontSize: 15px
    fontWeight: '400'
    lineHeight: 22px
    letterSpacing: 0em
  body-sm:
    fontFamily: Geist
    fontSize: 13px
    fontWeight: '400'
    lineHeight: 18px
    letterSpacing: 0.005em
  label-mono-lg:
    fontFamily: Geist
    fontSize: 24px
    fontWeight: '600'
    lineHeight: 28px
    letterSpacing: 0.04em
  label-mono-md:
    fontFamily: Geist
    fontSize: 14px
    fontWeight: '500'
    lineHeight: 18px
    letterSpacing: 0.02em
  label-mono-sm:
    fontFamily: Geist
    fontSize: 11px
    fontWeight: '500'
    lineHeight: 14px
    letterSpacing: 0.05em
rounded:
  sm: 0.125rem
  DEFAULT: 0.25rem
  md: 0.375rem
  lg: 0.5rem
  xl: 0.75rem
  full: 9999px
spacing:
  space-2xs: 2px
  space-xs: 4px
  space-sm: 8px
  space-md: 12px
  space-base: 16px
  space-lg: 24px
  space-xl: 32px
  space-2xl: 48px
  space-3xl: 64px
  touch-target-min: 48px
  touch-target-result: 64px
  container-admin-max: 1160px
  container-hall-max: 480px
---

## Brand & Style

The design system establishes an architectural, ultra-precise digital interface for competitive chess tournament operations. Borrowing from tournament chronometers (such as DGT digital clocks) and precision timing instruments, the visual language avoids decorative chess tropes (no skeuomorphic pieces, wood textures, or checkerboard motifs). Instead, chess logic is encoded structurally: disciplined geometry, tabular data streams, micro-contrast line borders, and binary color discs.

### Target Audiences & Context of Use
1. **The Hall App (Player Terminal)**: Players navigating dim, echoing tournament halls directly following exhaustive multi-hour rounds. Interaction demands instantaneous recognition, fault-tolerant tap surfaces (minimum 56px height), zero decorative latency, and pristine legibility at arm’s length under degraded mobile conditions.
2. **The Desk App (Arbiter Command)**: Arbiters operating high-density data tables across prolonged tournament weekends. The interface functions as an executive audit log prioritizing exceptions (disputes, missing submissions, system sync delays) with hotkey velocity and uncompromising legibility.

### Design Movement
**Minimalist Architectural Functionalism**: Crisp 1px hairline structural grids, obsidian-black surfaces contrasted with surgical whites, and stark typographic hierarchies. Chromatic color is reserved strictly for operational states (empty, pending, disputed, confirmed) and critical single-path CTAs.

## Colors

Color functions as semantic data rather than decorative trim. Background layers are keyed to physical environments: pure obsidian (`#0B0F17`) for the low-glare player hall interface, and balanced crisp slate (`#F8FAFC`) for the arbiter desk console.

### Semantic State Vocabularies
Status cues must remain accessible across lighting extremes and for color-deficient users through redundant visual tokens (geometry, status badges, and precise contrast):
- **Empty (Awaiting Result)**: Neutral Slate (`#64748B`). Low optical weight; denotes an active, uneventful board awaiting player submission.
- **Claimed / Pending (1 Submission Recorded)**: Amber Ochre (`#F59E0B`). High visibility; signals an unverified result entered by one device awaiting arbiter sign-off or opposing verification.
- **Disputed (Mismatched Submissions)**: Crimson / Rose (`#E11D48`). Demands priority arbitration; used in conjunction with split indicator chips and red border micro-pulses.
- **Confirmed / Released (Arbiter Certified)**: Emerald (`#059669`). Stable terminal state.

### Tournament Stepper Colors
- **Open**: Cobalt Precision Blue (`#2563EB`)
- **Released**: Warm Amber (`#D97706`)
- **Exported / Frozen**: Structural Slate (`#64748B`)

### Chess Piece Discs
Player colors are represented exclusively by 14px calibrated player discs:
- **White Disc**: `#FFFFFF` solid fill enclosed by a `#94A3B8` crisp hairline stroke.
- **Black Disc**: `#0F172A` deep obsidian fill enclosed by a `#475569` hairline stroke.

## Typography

The design system relies entirely on `Geist` to project an engineered, high-precision aesthetic. Type styles strictly enforce OpenType tabular figures (`font-variant-numeric: tabular-nums`) across all result values, board numbers, Elo ratings, timestamps, and 6-character room codes. This guarantees alignment and eliminates jitter when boards refresh dynamically.

### Hierarchy Guidelines
- **Scores & Result Indicators**: Formatted with `label-mono-lg` and tabular numerals (e.g., `1 : 0`, `½ : ½`, `0 : 1`). Punctuation colons use standardized tabular spacing.
- **Board Identifiers**: Highlighted via `label-mono-md` wrapped in compact boxed containers for rapid hall navigation.
- **Player Names**: Handled with `headline-sm` (mobile hall view) or `body-md` (desktop audit view) with explicit optical tracking to support long international names without truncation.

## Layout & Spacing

Layouts adhere to an absolute 4px/8px modular spacing scale configured for two discrete execution contexts:

### 1. Hall Mobile Layout (Touch & Arm's-Length Legibility)
- **Constraint**: Max-width capped at `480px` centered on mobile viewports; scales to a dual-column masonry layout on larger tablets.
- **Safe Zones**: Standard `16px` lateral margins with dynamic vertical margins calibrated to `env(safe-area-inset-bottom)` to protect bottom navigation and result buttons.
- **Touch Targets**: Normal interactive buttons have a strict minimum bounding box of `48px`. Result entry cards mandate an amplified `64px` height to prevent mis-taps.

### 2. Admin Desk View (High-Density Audit Table)
- **Constraint**: Fixed-width container at `1160px` centered, maximizing screen real estate on 13"–16" arbiter laptops.
- **Vertical Rhythm**: Dense `8px` and `12px` row padding inside pairing tables, presenting 20+ boards above the fold without sacrificing legibility or status clarity.

## Elevation & Depth

In alignment with the obsidian and tournament clock design philosophy, depth is established through **micro-contrast borders** and **flat surface-container steps** rather than diffuse drop shadows.

### Dark Theme (Hall App)
- **Base Canvas (Level 0)**: `#0B0F17` (Deep Obsidian).
- **Surface Level 1 (Card & Board Rows)**: `#131B2A` with a 1px boundary stroke of `#1E293B`.
- **Surface Level 2 (Modals & Menus)**: `#1E293B` bordered with `#334155`.
- **Focus & Interaction State**: Hairline edge illumination with `0 0 0 1px #2563EB`.

### Light Theme (Admin Console)
- **Base Canvas (Level 0)**: `#F8FAFC`.
- **Surface Level 1 (Data Cards & Tables)**: Pure White `#FFFFFF` with a crisp 1px boundary stroke of `#E2E8F0`.
- **Surface Level 2 (Floating Arbiter Sticky Bar)**: Pure White with a sharp hairline stroke (`#CBD5E1`) paired with an ambient grounding shadow: `0 4px 12px -2px rgba(15, 23, 42, 0.08)`.

## Shapes

The design system employs **Soft (Level 1)** geometric rounding. This sharp, controlled contouring reinforces the precision of hardware tournament timers, pairing sheet typography, and architectural geometry.

- **Base Radius (`rounded-sm`)**: `2px` for mini chips, tabular badges, and player disc container boxes.
- **Component Radius (`rounded`)**: `4px` for inputs, buttons, and individual pairing list rows.
- **Container Radius (`rounded-lg`)**: `8px` for modal dialogs, section summary cards, and QR posters.
- **Circular Indicators**: Exact `50%` (`rounded-full`) reserved strictly for White/Black player discs and stepper milestones.

## Components

### 1. Board Row Component
- **Structure**: Horizontal layout. Left: Board number in an architectural boxed frame (`label-mono-md`). Center: White and Black player pairings with their respective 14px discs (`disc-white-fill` / `disc-black-fill`). Right: Current status badge or real-time score.
- **Live Update Pulse**: When an updated result arrives via live-polling, the row triggers a 400ms background flash of `rgba(37, 99, 235, 0.2)` settling cleanly back to rest.

### 2. Result Choice Buttons (Hall View)
- **Structure**: Stack of three full-width tap targets (White wins `1 : 0`, Draw `½ : ½`, Black wins `0 : 1`).
- **Dimensions**: Fixed `64px` height, `4px` border radius, built with 1px border outlines.
- **Typography**: Primary score rendered in `label-mono-lg`; winning player name displayed as an immediate secondary confirmation sub-line in `body-sm`. Eliminates secondary confirmation dialogs.

### 3. State Chips
- **Tokens**: Compact badges (`4px` horizontal padding, `2px` vertical padding, `rounded-sm`).
- **Pairs**:
  - *Empty*: Gray dot + `AWAITING`.
  - *Claimed*: Amber pulsating dot (`#F59E0B`) + `ENTERED`.
  - *Disputed*: Crimson warning triangle (`#E11D48`) + `DISPUTE`.
  - *Confirmed*: Emerald check dot (`#059669`) + `RELEASED`.

### 4. Sequential Round Stepper
- **Layout**: 4-node progress track: `Imported` → `Entry Open` → `Released` → `Exported`.
- **States**: Finished milestones transition to Emerald `#059669`; active operations glow Cobalt `#2563EB`; future phases remain hairline slate frames. Timestamps sit tabular beneath each label.

### 5. Tournament Join QR Poster
- **Layout**: Clean print-optimized document (`#FFFFFF` background) with high-density vector QR code (240px square), bold 6-character tabular access code (`label-mono-lg`), and crisp instruction line in `Geist`. Designed for high-contrast visibility when taped to hall doors.