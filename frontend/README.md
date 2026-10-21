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
| Charts | Recharts |
| PWA | vite-plugin-pwa (installable; precaches the build only, never `/api`) |
| Tests | Vitest + Testing Library (unit and component), Playwright (end-to-end) |

## Getting started

Requires Node 22+ (developed on Node 24).

```bash
npm install
cp .env.example .env        # Windows: copy .env.example .env
npm run dev                 # http://localhost:5173
```

The dev server proxies `/api` to `VITE_DEV_PROXY_TARGET` (default `http://127.0.0.1:8000`), so run the FastAPI backend alongside it.

### Add shadcn components

```bash
npx shadcn@latest add <component>
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
| `npm test` | Run the Vitest suite once (jsdom; needs Node 22+) |
| `npm run test:watch` | Re-run tests on change |
| `npm run test:coverage` | Run the suite with coverage (HTML report in `coverage/`); fails below 85% of lines or 75% of branches |
| `npm run test:e2e` | Run the Playwright end-to-end tests (see below) |

## End-to-end tests

`e2e/` drives the production build in Chromium against the real backend on PostgreSQL, one
test per core journey: sign up (through the sign-up guide) and sign in, logging food, logging a meal photo (a real
photo scaled in the browser, estimated by the rule-based model, then confirmed), logging a
workout, and a weekly check-in whose proposal is applied. Each test signs up its own user, so the database
doesn't need to be empty. Any 5xx from the API fails the test, even if the page recovers.

`npm run test:e2e` builds the app, serves it with `vite preview` on port 4173 (proxying
`/api` as CloudFront would), and starts the backend on port 8001 after migrating the
database. With the compose PostgreSQL running, create the database once:

```bash
docker compose exec postgres createdb -U macrorep macrorep_e2e
npx playwright install chromium   # once
npm run test:e2e
```

Set `E2E_DATABASE_URL` to use another database. A failed test keeps a trace in
`test-results/` (`npx playwright show-trace <path>`).

## Environment variables

| Variable | Purpose |
|---|---|
| `VITE_API_BASE_URL` | Backend base URL. Leave empty to use the dev proxy. |
| `VITE_DEV_PROXY_TARGET` | Where `/api` is proxied during `npm run dev`. |

Anything prefixed `VITE_` is bundled into the browser — never put secrets here.

## Project structure

```
frontend/
├── public/                 # Static files served as-is (PWA icons — placeholders, replace with final art)
├── src/
│   ├── api/                # axios client and typed endpoint modules
│   ├── components/
│   │   ├── ui/             # shadcn-generated primitives
│   │   ├── layout/         # App shell, sidebar, bottom tab bar, page header
│   │   ├── charts/         # Calorie ring, macro bars, weight trend, volume
│   │   ├── food/           # Meal sections, food rows, quick add, custom food
│   │   ├── workout/        # Exercise card, set rows, rest timer
│   │   ├── coach/          # Check-in pipeline, proposal cards, chat
│   │   └── progress/       # Stat tiles, lift rows, check-in history
│   ├── hooks/              # Reusable hooks (use-media-query, data hooks)
│   ├── lib/                # Utilities (cn, macro maths, formatting, auth)
│   ├── pages/              # One component per route
│   ├── types/              # Shared TypeScript types
│   ├── App.tsx             # Routes
│   ├── main.tsx            # Providers and entry point
│   └── index.css           # Tailwind + design tokens
├── e2e/                    # Playwright end-to-end tests
├── components.json         # shadcn config
├── playwright.config.ts
├── vite.config.ts
└── tsconfig*.json
```

Conventions:

- File names are kebab-case (`app-shell.tsx`); components are PascalCase.
- Import from `src` with the `@/` alias.
- Unit tests sit next to the file they test (`macros.test.ts`).
- Layout responds to Tailwind breakpoints: `md` (768px) switches mobile → desktop.
