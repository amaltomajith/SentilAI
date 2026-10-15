# Design system

Direction: **terminal couture**. A command-line identity (mono labels, a `>` prompt, scanlines, pixel tags) built with the restraint of a premium product: layered green-black grounds, one accent, hairline borders, generous space. Reference mood: pixel-art stickers, CRT texture and a menu that opens as a card.

## Rules (do not break)
- **One locked dark theme.** The brief is a black and green terminal identity, so there is no light mode. Sections never invert.
- **Palette.** Grounds are green-tinted blacks (`bg`, `surface-1/2/3`), deep greens (`forest`, `moss`) are used as large fields, **one accent** (`primary`, signal green) is used for action and emphasis, text is `bone` (never pure white) with `muted-foreground` and `faint` below it. Brick (`destructive`) and amber (`warning`) mean state only (scammer, violation, caution). No pure black, no pure white, no purple, no neon glow shadows.
- **Type.** Geist for display and body (tight tracking, weight 600 for display), Geist Mono for chat meta, numbers and labels, Silkscreen only for tiny pixel tags. All self-hosted via `@fontsource`; no external font requests. No serif.
- **Shape.** Radius is 4px everywhere (`--radius`). Use 1px hairlines (`border-line`, `border-line-strong`) instead of nesting cards.
- **Materials.** `.panel` and `.panel-raised` (lit top edge, tinted shadow), `.field-forest` and `.field-moss` for large colored fields, `.crt-screen` for a framed local screen. The page-level `.crt-overlay` is a fixed, non-interactive layer of faint scanlines and vignette. It is deliberately cheap (no blend modes, no animation, no blur filters): those made the page stall in testing.
- **Icons.** `@phosphor-icons/react` only. Pixel art uses the procedural sprites in `src/components/pixel/Sprite.tsx` (12x12 bitmaps, outline computed from the silhouette). Add a sprite by adding a 12x12 grid; `src/test/sprites.test.ts` checks the format.
- **Images.** Real assets only: screenshots rendered by our own backend (`python -m scripts.render_samples` writes `public/img/`), real chat components for previews. No stock photos, no div-faked screenshots.
- **Copy.** No em or en dashes anywhere (a test enforces it on the landing page), no filler verbs, no invented statistics: numbers on the landing page come from `docs/BENCHMARKS.md` and say so. One label per intent ("Get started" for sign-up everywhere).
- **Motion.** Every animation must communicate something: hero entrance (hierarchy), the scripted chat (shows the product), sticky step rail (storytelling), hover and press feedback, one marquee (breadth of scam types). All of it honours `prefers-reduced-motion`. Scroll effects use Motion hooks or IntersectionObserver, never scroll listeners.
- **Layout.** Landing page sections each use a different layout family (split hero, marquee, sticky split-scroll, bento with exactly five cells, typographic statements, big figures, accordion, CTA band). Eyebrow labels are avoided; headlines carry the section.

## Where things live
`src/index.css` (tokens and utilities), `tailwind.config.ts` (mapping), `src/components/ui/*` (restyled shadcn primitives), `src/components/chat/Bubble.tsx` (shared by the landing demo and the app), `src/components/landing/*` and `src/pages/Landing.tsx`, `src/components/AppHeader.tsx` and `Shell.tsx` (app frame and mobile tab bar), `src/components/ConversationTab.tsx` and `Instruments.tsx` (chat), `src/lib/auth.tsx` (Clerk appearance themed with the same tokens).

## Checking a change
`npx tsc --noEmit -p tsconfig.app.json`, `npx eslint src`, `npx vitest run`, `npx vite build`; then look at `/`, `/onboarding`, `/practice`, `/connect`, `/live` at desktop and at 390px wide and confirm there is no horizontal scroll.