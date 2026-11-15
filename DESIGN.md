# SafeDay design system

SafeDay is an add-on inside Income Insurance's SmartBiz 360. It must look like it belongs inside Income's site, made with more care. Live reference: `/styleguide/` on the running API.

## Scene

- Insurer staff use the dashboards and the tariff desk on office laptops in daylight. The pitch shows them on a projector in a bright hall. Light theme is the default. Dark theme stays behind the toggle.
- Business owners (hawkers, shop owners, delivery riders) buy cover on a phone, often outdoors. The buy flow and the business owner dashboard must work at 375px wide with 44px touch targets.

## Files

| File | Holds |
|---|---|
| `api/site/theme.css` | Fonts, colour scales, semantic tokens, type, spacing, radius, motion, base elements, day chips |
| `api/site/ui.css` | Shared components: header, icons, buttons, fields, segmented control, cards, KPI strip, data tables, chips, notices, empty and loading states, tooltip, drawer, tier cards, footer |
| `api/site/ui.js` | `SafeUI.icon(name)`, `SafeUI.help(text)`, `SafeUI.openDrawer({title, subtitle, body})`, `SafeUI.sortable(table)`, tooltips for any `[data-tip]` |
| `api/site/{landing,auth,buy,dashboard}.css` | One page each. Only that page's layout and parts |
| `api/admin/admin.css`, `api/map/map.css` | Tariff desk and risk atlas. They link `theme.css` and use its tokens |
| `api/site/vendor/` | Ubuntu and Ubuntu Mono (woff2, Ubuntu Font Licence), `icons.svg` (Lucide 1.66.0, ISC) |

Link order on every page: `theme.css`, `ui.css`, the page stylesheet, then `ui.js` (defer) before the page script. Bump the `?v=` number on any file you change.

## Colour

Strategy: restrained. Warm neutrals carry the page. Orange is for actions, the current selection and the brand mark only. Blue is for information and secondary data, never for an action.

| Token | Use |
|---|---|
| `--bg` | Page background (warm off-white) |
| `--surface` | Cards, header, tables, drawer |
| `--surface-2` | Table header, quiet panels inside a surface |
| `--sunken` | Segmented control track, neutral chips, skeletons, hover on ghost buttons |
| `--ink`, `--ink-2`, `--muted` | Text: primary, secondary, tertiary. `--muted` is the lightest allowed for text |
| `--faint` | Icons and decoration only. Never text (3.5:1) |
| `--line`, `--line-strong` | Hairlines; input and button borders |
| `--accent`, `--accent-hover`, `--accent-press` | Primary buttons, links, selected state |
| `--accent-fill` | Non-text fills: brand mark, progress bars, chart bars |
| `--accent-soft`, `--accent-soft-2`, `--accent-line` | Selected rows, recommended tier, soft buttons |
| `--info`, `--info-soft` | Info notices, demo tags, secondary data series |
| `--good`, `--warning`, `--serious`, `--critical` and `-soft` | Status only |
| `--heat`, `--rain`, `--haze`, `--flood`, `--closure` | Hazards only, same in both themes |

Rules:
- Body and placeholder text pass 4.5:1. Accent text on `--sunken` is 4.1:1, so do not put orange text on `--sunken`.
- Never hard-code a hex value in a page stylesheet. Use a token. If a token is missing, add it to `theme.css`.
- Colour is never the only signal. Status pills carry a word, and day chips carry a dot and a word.

## Type

- One family: Ubuntu, weights 300 (display only), 400 (body), 500 (labels, buttons, table headers), 700 (headings, KPI values).
- Ubuntu Mono for numbers in tables and KPI values (`.num`) only. It is never decoration.
- Scale: 12, 14, 16, 18, 20, 24, 32, 40 px (`--t-xs` to `--t-3xl`). `--t-display` is for the landing hero only.
- Page title: `.page-title` (32 bold). Section: 24 bold. Card title: 20 bold. Body 16. Fine print 14 `--muted`.
- Headings use `text-wrap: balance`. Letter spacing is no tighter than -0.03em.
- Prose lines stay between 65 and 75 characters.

## Space and shape

- Spacing steps: 4, 8, 12, 16, 24, 32, 48, 64 (`--s-1` to `--s-8`). There is more space above a heading than below it.
- Radius: 8 for inputs and small controls, 12 for table frames and notices, 16 for cards, pill for buttons and chips.
- Elevation: use a border OR a shadow, never both. Cards: 1px `--line`. Raised: `--shadow-1`. Popovers and drawers: `--shadow-2` and `--shadow-3`.
- Page width: `--page-max` (1200px). Gutters: 24px, or 16px at 640px and below.

## Icons

Lucide, from the sprite: `<svg class="i" aria-hidden="true"><use href="/vendor/icons.svg#NAME"/></svg>`, or `SafeUI.icon("NAME")` in JavaScript. The sprite holds these 32 icons: arrow-up-down banknote bike building-2 calendar check chevron-down chevron-left chevron-right circle-alert clock cloud-fog cloud-rain external-link funnel info log-out map map-pin maximize-2 moon plus search shield-check sliders-horizontal store sun thermometer-sun triangle-alert users waves x. Never use emoji or text glyphs (☾, ✓, ↗) as icons. To add an icon, add its SVG from lucide-static 1.66.0 as a `<symbol>` in `icons.svg`.

## Components (markup in /styleguide/)

- **Header**: `header.topnav` with `a.brand` (`.brand-mark` + "SafeDay"), then `nav` holding links (icon + `span.label-wide`), `.who` (`.avatar` initials + `span.who-text`), the theme toggle (`.theme-toggle` with the moon or sun icon) and Sign out (`.btn.small`). Below 720px the text labels hide and only the icons stay. Mark the current page with `aria-current="page"`.
- **Buttons**: `.btn` (secondary), `.btn.primary` (one per view), `.btn.secondary` (soft orange), `.btn.ghost`, `.btn.quiet` (link-style), `.btn.danger`, sizes `.small` and `.large`, `.icon-btn`. Loading: `aria-busy="true"`. They scale to 0.97 on press.
- **Fields**: a `label` wraps its text and its control. Hint text goes in `span.hint`. An invalid field gets `aria-invalid="true"` and the error says what to do. Search fields use `.input-icon`.
- **Segmented control**: `.segmented` with buttons. Selected: `.on` or `aria-selected` or `aria-pressed`.
- **Cards**: `.card`, `.card.raised`, `.card.flush` (for a table or empty state), `.card-head` (title + actions). Never nest cards. Never build a page as a grid of same-size icon cards.
- **KPI strip**: `.kpis > .kpi > .k/.v/.n`. It is one surface with hairline dividers. Use `.num` on the value. Show `.skeleton.value` while loading. Add `SafeUI.help(text)` next to a label that needs it.
- **Data table**: `.table-tools` (search, filter selects, `.count`), then `.table-wrap > table.data`. Sortable headers: `th > button.sort` with the arrow-up-down icon, and `SafeUI.sortable(table)`. Numbers: `.num` and `data-value` for raw values. A clickable row gets `.clickable`, is reachable with the keyboard, and opens the drawer.
- **Chips**: `.chip` and `.status-pill` with `.good`, `.warning`, `.critical`, `.info`, `.accent`, `.muted`. Day colours: `.day-chip.day-green/yellow/red/none`. Demo rows get `span.demo-tag` with the text "demo".
- **Notices**: `p.notice` (+ `.warning`, `.critical`, `.accent`), an icon first, then the text. Never use a thick coloured side border.
- **Empty state**: `.empty` with an icon, `h3`, one sentence that says what will appear and how, and an action if one exists.
- **Loading**: `.skeleton` blocks in the shape of the content. `.loading` (spinner + text) only for a whole page.
- **Tooltip**: any element with `data-tip` and the same `aria-label`. `SafeUI.help(text)` makes an info button. The tooltip floats above tables and never gets clipped.
- **Drawer**: `SafeUI.openDrawer({title, subtitle, body})` opens a right side panel (a `<dialog>`). Esc, the X button and a click on the backdrop close it. Use it for detail views. Do not use a centred modal unless the task must interrupt the user.
- **Tier cards**: `.tiers-row > button.tier-card`. Selected or recommended: `aria-checked="true"` or `.rec`.

## Motion

- Curves: `--ease-out` (enter, press), `--ease-in-out` (move on screen), `--ease-drawer` (drawer). Durations: press 140ms, hover/colour 160ms, small UI 220ms, drawer 300ms. Exit is faster than enter.
- Animate only `transform` and `opacity`, plus colour on hover.
- Hover effects go inside `@media (hover: hover) and (pointer: fine)`.
- No page-load sequences. No animation on actions used many times a minute (sorting, filtering, typing).
- `prefers-reduced-motion` is handled globally in `theme.css`: movement stops, but colour and opacity changes stay.

## Every screen ships with

- Default, hover, focus-visible, active, disabled, loading, empty and error states for everything interactive.
- Real copy in plain words. Buttons name the action. Errors say what went wrong and what to do.
- No horizontal page scroll at 375px. Tables scroll inside `.table-wrap`.
- Keyboard: every action reachable with Tab, a visible focus ring, Esc closes the drawer.
- Made-up data labelled as demo (AGENTS.md: synthetic data is labelled).

## Never

- Eyebrow or kicker labels above headings. Section numbers as decoration.
- Gradient text. Glass or blur as decoration. Hard offset shadows. Side stripes thicker than 1px.
- A border and a wide shadow on the same card. Nested cards.
- Emoji or Unicode glyphs as icons.
- New hex values in page stylesheets. A UI framework or a build step.
