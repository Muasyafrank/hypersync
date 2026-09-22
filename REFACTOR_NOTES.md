# Refactor notes

Functionality is unchanged. Everything below is a correctness, structure,
performance or accessibility change.

## Bugs fixed

1. **Alerts were never persisted.** `create_reading` committed the reading,
   then called `maybe_create_alert`, which does `db.add()` + `db.flush()`
   with no commit after it. The session closed and the alert was discarded,
   so the clinician alert queue was empty by construction. The reading and
   the alert are now written in one transaction.

2. **The recommendations endpoint always failed for at-risk patients.**
   The router imported `core/recommendation_engine.py`, which loads
   `ml/models/recommendation_model.joblib` — a file that does not exist
   (the trained artefact is `bp_status_model.joblib`). Any patient with an
   elevated or high trend got a 500, silently swallowed by the dashboard's
   `.catch(() => {})`. The real STEPS-trained engine,
   `core/ml_recommendation_engine.py`, was imported by nothing. The router
   now uses it and the stale module is deleted.

3. **Logout never revoked the refresh token.** `AuthContext.logout` called
   `logoutUser`, which was never imported — `api/auth.js` exported it as
   `log`. An empty `catch {}` hid the `ReferenceError`.

4. **Classification disagreed across the stack.** The frontend treated
   diastolic ≥ 95 as high; the backend used ≥ 90. The live preview
   contradicted the saved status. Both now derive from one documented set
   of thresholds.

5. **Admin "Create clinician" had uncontrolled inputs** — the email field
   had no `value` and the password field's `value` was commented out, so
   the form never cleared and React warned on every render.

6. **The reset-password modal had no way to open it.** It was fully built,
   with API function and handlers, but no control rendered `openReset`.
   A key icon now sits alongside view/edit/delete.

7. **`LogReading` number inputs had `type="number"` commented out**, so
   mobile users got a text keyboard and no browser-level range validation.

8. `update_user` returned **404** for "cannot change your own role"
   (now 400), and `api/admin.js#updateUser` returned nothing.

## Performance

- **Clinician dashboard N+1 removed.** It fetched every patient's complete
  reading history — one request per patient — to display the latest one.
  New endpoint `GET /users/patients/summary` returns all patients with
  their latest reading and count in three queries total.
- **Recommendations no longer written on every page load.** The GET
  endpoint persisted a fresh batch each time the dashboard mounted, growing
  the table without bound. It now reuses a batch for 12 hours.
- **Route-level code splitting.** A patient no longer downloads the admin
  and clinician screens. Recharts (~400 kB) is a separate chunk.
- `joinedload` on the alerts query removes a per-alert lookup for
  `patient_name`.
- Connection pooling with `pool_pre_ping` so stale connections fail fast.
- `useAsync` discards responses that arrive after unmount or after the
  dependencies change, preventing stale renders and state-after-unmount.

## Structure

**Backend**

- Role checks moved from route bodies into dependencies
  (`require_patient` / `require_clinician` / `require_admin`), so they are
  declared in the signature and documented in OpenAPI.
- `deps.py` no longer calls `uuid.UUID()` on unvalidated token claims,
  which turned a malformed token into a 500 instead of a 401.
- `notes` is properly `str | None` rather than being coerced to `" "`.
- CORS origins, token lifetimes and algorithm are configuration, not
  literals in `main.py`.
- Trailing-slash routes normalised, so requests no longer take a 307.

**Frontend**

- Deleted `pages/Readings.jsx` — 221 lines, unrouted, a dead duplicate of
  `LogReading` + `ReadingsHistory` with its own navbar and stale validation
  ranges.
- New `components/ui/`: `Panel`, `PageHeader`, `StatCard`, `StatusPill`,
  `RoleBadge`, `DataRow`, `EmptyState`, `ErrorState`, `Loader`. These
  absorb the inline style objects that were repeated across every page.
- New `hooks/useAsync` and `hooks/useForm` replace the fetch-and-form
  boilerplate that was copy-pasted into nearly every page.
- New `utils/format.js` — the same `toLocaleString` option objects were
  written out in five separate files.
- `BPTrendChart` replaces two near-identical Recharts definitions.
- `AdminDashboard` went from 392 lines to ~180; its four modals are now
  components.
- The Lifestyle wizard's step and entry rendering moved into
  `components/lifestyle/`.
- `Layout`'s nav is data instead of nested ternaries, and patients finally
  have an Alerts link (the route existed but nothing linked to it).
- Added an `ErrorBoundary` so one broken page can't blank the app.

## Accessibility

- Clickable rows are real `<button>`s, so they are keyboard-reachable and
  focusable; visible focus rings added.
- Form controls have labels and ids; icon-only buttons have `aria-label`s.
- The lifestyle wizard progress bar exposes `role="progressbar"` with
  position, and choice buttons expose `aria-pressed`.
- The live preview panel is `aria-live="polite"`.
- `prefers-reduced-motion` is respected.

## Security / hygiene

- `backend/.env.example` was committed containing what appear to be real
  database and signing credentials. Replaced with placeholders.
  **Rotate `SECRET_KEY` and the database password** — anything in git
  history should be treated as compromised.
- `.gitignore` now covers the virtualenv, model artefacts and raw data.
- Login failures return one generic message, so the form can't be used to
  enumerate registered email addresses.
- The axios refresh interceptor was rewritten: one shared in-flight refresh
  instead of a hand-rolled queue, and no redirect loop when already on
  `/login`.

## Not done

`frontend/src/theme.css` is 1,290 lines with heavy duplication —
`.btn-hs-primary` is defined nine times, `.hs-sidebar-link` six,
`.hs-reading-row` three. Later rules silently override earlier ones, so
much of the file is dead weight. New component classes were appended in a
clearly marked section rather than deduplicating the rest, because
verifying the visual result needs the app running. Suggested approach:
work through the duplicated selectors one at a time with the app open,
keeping the last definition of each and folding in any earlier declarations
it doesn't already set.
