# MacroRep — Handoff (draft)

> **Status:** Draft · Last updated 17 Sep 2026 (all pages built, unverified)
> **Scope:** Frontend only. Backend, auth and AI agents not started.

MacroRep is the CS464 project: a mobile-first web app for tracking nutrition and training, with a multi-agent AI "weekly check-in" that proposes changes to calorie targets and workout plans. Full product plan: `../plan.md`.

---

## 1. Where things are

| Item | Location |
|---|---|
| Frontend app | `MacroRep/frontend` |
| Product plan | `02 CS464 Fullstack Dev/plan.md` |
| UI design canvas (mobile + desktop, 14 screens) | [MacroRep UI Design](https://claude.ai/artifact/Wfnud6GP6M9qobNbxECxqc) — private; share from the canvas menu |
| Reference project (stack source) | `05 CS301 - Solution Architecture/projectRepo/cs301-20267-g3-ttt/frontend` |

---

## 2. Current status

| Area | Status | Notes |
|---|---|---|
| Project scaffold | ✅ Done | Vite + React + TS, Tailwind v4, shadcn/ui, routing, app shell |
| App shell | ✅ Done | Sidebar ≥768px, bottom tab bar <768px |
| **Food page** | 🟡 Built, needs verification | Latest refactor (axios + review fixes) not yet type-checked or run |
| **Home, Workout, Coach, Progress, Profile** | 🟡 Built 17 Sep, needs verification | Written without being able to run `npm` (see §10); typecheck/lint/build not yet run |
| API layer | 🟡 Mocked | axios client + in-memory mock adapter; no real backend |
| Auth | ⬜ Not started | Plan: OAuth2-style flow + JWT (interceptor has a TODO) |
| PWA | ⬜ Not started | `vite-plugin-pwa` installed, not configured |
| Tests | ⬜ Not started | Vitest, Testing Library, Playwright installed; no tests or config |
| CI | ⬜ Not started | |

**First thing to do:** run `npm run typecheck` and `npm run dev`, then exercise the Food page (checklist in §8).

---

## 3. Getting started

Requires Node 22+ (developed on 24.20.0).

```bash
cd MacroRep/frontend
npm install
cp .env.example .env        # Windows: copy .env.example .env
npm run dev                 # http://localhost:5173
```

| Script | Purpose |
|---|---|
| `npm run dev` | Dev server (mock API on by default) |
| `npm run typecheck` | `tsc -b --noEmit` |
| `npm run lint` | oxlint |
| `npm run build` | Type-check + production build |

| Env var | Purpose |
|---|---|
| `VITE_API_BASE_URL` | Backend base URL. Empty → `/api` via the Vite proxy |
| `VITE_DEV_PROXY_TARGET` | Proxy target for `/api` in dev (default `http://127.0.0.1:8000`) |
| `VITE_USE_MOCK_API` | `true`/`false`. Defaults to `true` in dev |

Never put secrets in `VITE_*` variables — they ship to the browser.

---

## 4. Tech stack

| Layer | Choice |
|---|---|
| Framework | React 19 + TypeScript 6 (strict) |
| Build | Vite 8 |
| Styling | Tailwind CSS v4, CSS variables in `src/index.css` |
| Components | shadcn/ui (`radix-nova` style, Radix primitives), lucide-react icons |
| Routing | React Router 7 (lazy-loaded pages) |
| Server state | TanStack Query 5 |
| HTTP | axios |
| Forms | React Hook Form + Zod (v3 API) + `@hookform/resolvers` |
| Feedback | sonner toasts |
| Dates | date-fns |
| Lint | oxlint |
| Installed, not wired up | vite-plugin-pwa, Vitest, Testing Library, Playwright, Recharts |

---

## 5. Architecture

### Data flow

```
Page (pages/food-page.tsx)
  └─ TanStack Query hooks        hooks/use-food-log.ts
       └─ Typed API functions    api/food-api.ts
            └─ axios instance    api/client.ts
                 └─ adapter:     api/mock/mock-adapter.ts   (dev, until backend exists)
                                 → FastAPI                  (VITE_USE_MOCK_API=false)
```

- **Mock adapter** answers requests in memory with ~350 ms latency, so loading states are visible. It is dynamically imported and excluded from production builds. Seed data: `src/data/sample-food.ts`.
- **Query keys** live in `api/query-keys.ts`.
- **Mutations** (add/remove entry) update the cache optimistically and roll back on error; custom food creation invalidates search results.
- **Errors** are turned into user-facing text by `apiErrorMessage()` in `api/client.ts`.

### Endpoints the frontend expects

Mirrored by the mock. The backend should match these, or `food-api.ts` should be updated.

| Method | Path | Request | Response |
|---|---|---|---|
| GET | `/api/food-log?date=yyyy-MM-dd` | — | `{ date, entries: FoodEntry[] }` |
| POST | `/api/food-log/entries` | `FoodEntry` without `id`, plus `date` | `FoodEntry` (201) |
| DELETE | `/api/food-log/entries/{id}` | — | 204 |
| GET | `/api/foods?q=&limit=8` | — | `Food[]` |
| POST | `/api/foods` | `Food` without `id`, `source` | `Food` (201) |
| GET | `/api/nutrition/targets` | — | `{ calories, protein, carbs, fat }` |

| PUT | `/api/nutrition/targets` | `{ calories, protein, carbs, fat }` | same |
| GET | `/api/nutrition/daily-calories?days=7` | — | `{ date, calories }[]` |
| GET | `/api/workouts/today` | — | `PlannedWorkout \| null` (null = rest day) |
| GET | `/api/exercises?q=&muscle=&equipment=&limit=30` | — | `Exercise[]` (custom first; includes `lastSession`) |
| POST | `/api/exercises` | `{ name, equipment, muscles }` | `Exercise` (201; 409 if the name exists) |
| POST | `/api/workouts/sessions` | `FinishWorkoutInput` (`planId` null for an empty workout) | `WorkoutSummary` (201); updates each exercise's `lastSession` |
| GET | `/api/progress?range=1M\|3M\|6M\|1Y\|All` | — | `ProgressResponse` |
| POST | `/api/body/weigh-ins` | `{ date, weightKg }` | `WeightPoint` (201) |
| GET | `/api/coach/check-ins/current` | — | `CheckIn \| null` |
| POST | `/api/coach/check-ins/{id}/proposals/{pid}/decision` | `{ decision: "apply"\|"reject", changes? }` | `Proposal` |
| POST | `/api/coach/check-ins/{id}/messages` | `{ text }` | `CoachMessage` |
| GET / PUT | `/api/profile` | `UpdateProfileInput` | `Profile` |

Types: `src/types/{food,workout,progress,coach,profile}.ts`. Errors: FastAPI-style `{ detail: string }` with 4xx/5xx. Mock state lives in `api/mock/mock-db.ts`; non-food routes in `api/mock/extra-routes.ts`.

### Folder structure

```
src/
  api/            client, typed endpoints, query keys, mock/
  components/
    ui/           shadcn-generated (edit via CLI where possible)
    layout/       app shell, sidebar, tab bar, page header
    charts/       calorie ring, macro bars
    food/         food page components
    workout/ coach/ progress/   empty — next screens
  data/           sample data used by the mock
  hooks/          query hooks, media query, debounce
  lib/            cn, macro maths, formatting, food-log helpers
  pages/          one file per route
  types/          shared domain types
```

---

## 6. Conventions

These follow the shadcn, frontend-production-shadcn and Vercel React best-practice skills. Please keep to them.

**Components and styling**
- Use existing shadcn components before custom markup. Add missing ones with `npx shadcn@latest add <name>` and read the generated file before using it.
- Forms use `FieldGroup` / `Field` / `FieldSet`; inputs with units use `InputGroup`. Validation: `data-invalid` on `Field`, `aria-invalid` on the control.
- Option sets use `ToggleGroup`. Callouts use `Alert`; empty states use `Empty`; loading uses `Skeleton`; dividers use `Separator`.
- Icons in buttons use `data-icon="inline-start|inline-end"` with no size classes. Icon-only buttons need `aria-label`.
- Semantic tokens and component variants only; no raw colours or `dark:` overrides. Macro colours are tokens: `bg-protein`, `bg-carbs`, `bg-fat`, `bg-calories`.
- `gap-*` not `space-*`; `size-*` for square elements.
- Dialogs/drawers always have a title (use `sr-only` if hidden).

**React**
- Server data goes through TanStack Query hooks, never `useEffect` + `fetch`. All HTTP goes through `apiClient`.
- Derive values during render; reset per-item state with `key`, not effects.
- Components that watch form values (`useWatch`) should be small children so the whole form doesn't re-render.
- Use ternaries, not `&&`, when the condition can be a number.
- Overlays: `Drawer` below 1024px, `Dialog` or side panel at 1024px and up (`useMediaQuery(DESKTOP_QUERY)`).

**Files:** kebab-case file names, PascalCase components, `@/` import alias, tests next to the file they test.

---

## 7. Food page — what exists

- Daily summary: calories vs target, progress ring, protein/carbs/fat bars.
- Four meal sections with logged items and remove buttons; "Not logged" state.
- Search with a 250 ms debounce, serving editor (servings or grams), live macro preview.
- Quick add: calories + macros, auto-calculates calories, warns on mismatch.
- Custom food: name, brand, serving size/unit/weight, macros, optional fibre/sugar/sodium, desktop live preview, "Save only" or "Save & log".
- Day navigation (previous/next; future days disabled).
- Loading, error (with Retry), empty and saving states.
- Barcode and photo scan buttons show "coming soon" toasts.

---

## 8. Verification checklist (not yet done)

- [ ] `npm run typecheck` passes
- [ ] `npm run lint` passes
- [ ] `npm run build` passes
- [ ] Desktop (≥1024px): search panel on the right; meal "+" focuses search
- [ ] Mobile (<1024px): search and quick add open as bottom drawers
- [ ] Add a food → appears immediately, toast shown, totals update
- [ ] Remove a food → disappears immediately
- [ ] Quick add mismatch warning: "Use X kcal" and "Keep" both work
- [ ] Custom food: validation messages; saved food appears in search as "My food"
- [ ] Resize across 1024px while a dialog is open → input is kept
- [ ] Previous day shows empty meals; next-day button disabled on today
- [ ] No console errors; keyboard can reach every control
- [ ] Home: weigh-in saves and the reminder disappears; "Later" hides the check-in banner; desktop shows 7-day chart
- [ ] Workout: start screen offers plan and empty workout; Home "Start workout" skips it; tick a set → rest timer starts; ±15s/Skip work; Finish with sets left asks to confirm; summary shows; Discard returns to start screen
- [ ] Workout picker: search + filters, multi-select adds in order, "Last:" shown, no-results → create custom exercise (validation, duplicate name error) → added; custom appears first next time
- [ ] Workout editing: remove last set (disabled when done or only one), move up/down (disabled at ends), remove exercise → Undo restores position; finishing an empty workout updates "Last:" in the picker
- [ ] Coach: Apply / Reject update the badge immediately; Edit validates; Apply all; Food targets change after applying nutrition; chat replies
- [ ] Progress: range buttons change data and the URL; charts render at 390px; Export downloads a CSV
- [ ] Profile: save buttons disabled until edited; validation messages; Maintain disables the rate field

---

## 9. Known issues and limitations

- **Mock data resets** on page reload.
- **Stray placeholder files:** `.gitkeep` files remain in `src/types`, `src/components/food`, `src/components/charts` and `src/components/ui`. Safe to delete.
- **Two breakpoints:** app navigation switches at 768px; food page overlays switch at 1024px. Intentional for now, but worth reviewing.
- **`crypto.randomUUID`** is only used behind a fallback; fine on LAN IPs.
- **Sample nutrition values** are approximate and for UI only.
- **Exercise options use icon buttons** (remove set, move, remove) because `dropdown-menu` wasn't installed; consider `npx shadcn@latest add dropdown-menu` to tidy the card footer.
- **Unused shadcn component:** `sheet.tsx` (replaced by `drawer.tsx` on the Food page).
- **17 Sep pages are unverified:** they were written in a cloud session that couldn't install npm packages and couldn't run a shell on this PC, so no typecheck/lint/build/browser run happened. Expect a few type errors to fix (most likely spots: Recharts `Tooltip content` typing, `ToggleGroup` `disabled` prop, zod `preprocess` input types).
- **Workout session isn't persisted:** leaving the Workout page loses the in-progress session. Plan: keep it in a store or `sessionStorage` once the backend exists.
- **Coach chat history** is local component state; the "Later" dismissal on Home resets on navigation.
- **`shadcn` CLI not used** for charts (see §8b); consider `npx shadcn@latest add chart` and migrating.

---

## 10. Next steps (suggested order)

1. Run the verification checklist in §8 and fix anything found.
2. Run typecheck/lint/build on the 17 Sep pages and fix errors; walk the new checklist items.
3. Persist the in-progress workout session (still lost on navigation). Later: save workouts as templates.
4. Consider migrating charts to shadcn `Chart`.
5. Agree the new endpoints in §6 with the backend.
6. Add Vitest config + first tests (`lib/macros.ts`, `lib/food-log.ts`, quick add validation).
7. Configure `vite-plugin-pwa` (manifest, icons, static-asset caching only).
8. Agree API contracts with the backend and switch `VITE_USE_MOCK_API=false`.
9. Add auth: login flow, JWT in the axios interceptor, protected routes.

---

## 11. Open questions

- Backend owner and timeline for the food endpoints in §5?
- Units: metric only, or support lb/oz?
- Should custom foods be private per user or shareable?
- Food database source (e.g. a public nutrition API vs. seeded data)?
- Hosting target for the frontend (affects PWA and env setup)?
