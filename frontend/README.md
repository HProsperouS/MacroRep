# MacroRep — Frontend

Mobile-first web app for MacroRep: nutrition logging, workout tracking and multi-agent weekly check-ins.
One responsive codebase — bottom tab bar on mobile, sidebar on desktop.

## Stack

| Layer | Choice |
|---|---|
| Framework | React 19 + TypeScript |
| Build | Vite |
| Styling | Tailwind CSS v4 + shadcn/ui (Radix) |
| Routing | React Router |
| Server state | TanStack Query |
| HTTP | axios |
| Forms | React Hook Form + Zod |
| Icons / toasts | lucide-react, sonner |
| Lint | oxlint |
| Planned | vite-plugin-pwa, Vitest + Testing Library, Playwright, Recharts |

## Getting started

Requires Node 22+ (developed on Node 24).

```bash
npm install
cp .env.example .env        # Windows: copy .env.example .env
npm run dev                 # http://localhost:5173
```

The dev server proxies `/api` to `VITE_DEV_PROXY_TARGET` (default `http://127.0.0.1:8000`), so run the FastAPI backend alongside it.

### Add remaining packages

```bash
npm i recharts @fontsource/barlow-condensed
npm i -D vite-plugin-pwa vitest @testing-library/react @testing-library/jest-dom @testing-library/user-event jsdom @playwright/test
```

### Add shadcn components

```bash
npx shadcn@latest add button card input label select sheet dialog tabs switch badge progress skeleton sonner tooltip
```

Components are generated into `src/components/ui` — edit them freely.

## Scripts

| Script | What it does |
|---|---|
| `npm run dev` | Start the Vite dev server |
| `npm run build` | Type-check and build to `dist/` |
| `npm run preview` | Serve the production build locally |
| `npm run lint` | Lint with oxlint |
| `npm run typecheck` | Type-check without emitting |

## Environment variables

| Variable | Purpose |
|---|---|
| `VITE_API_BASE_URL` | Backend base URL. Leave empty to use the dev proxy. |
| `VITE_DEV_PROXY_TARGET` | Where `/api` is proxied during `npm run dev`. |

Anything prefixed `VITE_` is bundled into the browser — never put secrets here.

## Project structure

```
frontend/
├── e2e/                    # Playwright end-to-end tests
├── public/                 # Static files served as-is (favicon, PWA icons)
├── src/
│   ├── api/                # axios client and typed endpoint modules
│   ├── assets/             # Images and files imported by code
│   ├── components/
│   │   ├── ui/             # shadcn-generated primitives
│   │   ├── layout/         # App shell, sidebar, bottom tab bar, page header
│   │   ├── charts/         # Calorie ring, macro bars, weight trend, volume
│   │   ├── food/           # Meal sections, food rows, quick add, custom food
│   │   ├── workout/        # Exercise card, set rows, rest timer
│   │   ├── coach/          # Check-in pipeline, proposal cards, chat
│   │   └── progress/       # Stat tiles, lift rows, check-in history
│   ├── hooks/              # Reusable hooks (use-mobile, data hooks)
│   ├── lib/                # Utilities (cn, macro maths, formatting, auth)
│   ├── pages/              # One component per route
│   ├── types/              # Shared TypeScript types
│   ├── App.tsx             # Routes
│   ├── main.tsx            # Providers and entry point
│   └── index.css           # Tailwind + design tokens
├── components.json         # shadcn config
├── vite.config.ts
└── tsconfig*.json
```

Conventions:

- File names are kebab-case (`app-shell.tsx`); components are PascalCase.
- Import from `src` with the `@/` alias.
- Unit tests sit next to the file they test (`macros.test.ts`).
- Layout responds to Tailwind breakpoints: `md` (768px) switches mobile → desktop.
