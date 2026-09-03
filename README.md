# Jewellery Bill Generator — Full-Stack Edition

A secure, persistent, mobile-friendly jewellery billing app: a static HTML/CSS/JS
frontend backed by a FastAPI + PostgreSQL API. Converted from the original
single-file prototype (`bill-generator (1).html`) while preserving its visual
identity (maroon/gold/cream), calculations, and print/PDF output.

```
Frontend (HTML/CSS/JS) → REST API (FastAPI) → PostgreSQL
```

## 1. Folder structure

```
jewellery-bill-generator/
├── frontend/
│   └── index.html          # the app (login + create bill + records)
├── backend/
│   ├── app/
│   │   ├── main.py         # FastAPI app, CORS, error handlers, health check
│   │   ├── database.py     # SQLAlchemy engine/session
│   │   ├── models.py       # ORM models (bills, bill_items, admin_users, sessions)
│   │   ├── schemas.py      # Pydantic request/response validation
│   │   ├── auth.py         # session cookie auth dependency, admin bootstrap
│   │   ├── security.py     # Argon2 password hashing, login rate limiting
│   │   └── routers/
│   │       ├── auth.py     # /api/auth/*
│   │       └── bills.py    # /api/bills/*
│   ├── requirements.txt
│   └── .env.example
├── README.md
└── .gitignore
```

## 2. Files created / modified

* All backend files above are new.
* `frontend/index.html` is the original prototype with: a login screen,
  an API layer (`apiRequest`), backend-driven bill numbering, records
  fetched from PostgreSQL instead of a JS array, search/filter UI,
  edit/delete against the API, loading + error states, and added mobile
  CSS (records become stacked cards, touch-friendly buttons, horizontal
  scroll for the printable items table on narrow screens). The item
  editor, live bill preview, calculations, print, and PDF export are
  functionally unchanged from the original.

## 3. Database schema

**admin_users** — single shop-owner login. `password_hash` only (Argon2);
plaintext password is never stored.

**sessions** — server-side session store backing the HttpOnly cookie
(`token`, `admin_id`, `expires_at`).

**bills** — `id` (also used as the bill number), `bill_date`, customer
fields, a snapshot of shop details at the time the bill was created,
`subtotal` / `cgst_percent` / `sgst_percent` / `cgst_amount` /
`sgst_amount` / `grand_total` / `received_online` / `received_cash` /
`due_amount` / `payment_mode`, `note`, `terms`, optional `stamp_image`
(base64), `created_at`, `updated_at`. Money columns are `NUMERIC(14,2)`
(no floats); weights are `NUMERIC(12,3)`.

**bill_items** — `id`, `bill_id` (FK → `bills.id`, `ON DELETE CASCADE`),
`item_name`, `gross_weight`, `less_weight`, `net_weight`, `rate`,
`labour`, `item_total`.

Deleting a bill cascades to its items automatically (both via the FK and
the SQLAlchemy relationship).

## 4. API endpoints

```
GET    /api/health              → { "status": "ok" }

POST   /api/auth/login           { "password": "..." } → sets HttpOnly session cookie
POST   /api/auth/logout
GET    /api/auth/me

POST   /api/bills                create bill (+ items), server assigns bill number
GET    /api/bills                list/search bills
                                  query params: bill_number, customer_name,
                                  customer_mobile, date_from, date_to
GET    /api/bills/{id}           full bill detail
PUT    /api/bills/{id}           update bill (keeps the same bill number)
DELETE /api/bills/{id}           delete bill + its items
```

All `/api/bills/*` endpoints require a valid session (401 otherwise).

## 5. Authentication

* Single admin account, password-only login (matches the original app's
  login screen design).
* Password is hashed with **Argon2** (`argon2-cffi`) and stored in
  `admin_users.password_hash`. The plaintext is never written to disk or
  logged.
* On first startup, if no admin row exists, the server hashes the
  `ADMIN_PASSWORD` environment variable once and stores the hash. Remove
  or rotate that env var after first boot.
* Sessions are server-side rows (`sessions` table) referenced by an
  HttpOnly, `SameSite=Lax` cookie. In production (`COOKIE_SECURE=true`,
  the default) the cookie is also marked `Secure`, so it is only sent
  over HTTPS.
* `/api/bills/*` is protected by a FastAPI dependency
  (`get_current_admin`) that rejects requests without a valid,
  unexpired session with `401 Unauthorized`.
* A simple in-memory rate limiter blocks an IP after 5 failed login
  attempts within 15 minutes (`429 Too Many Requests`). This is a
  best-effort, single-process mitigation — for a multi-instance
  deployment, back it with Redis instead.

## 6. Automatic bill numbering

The bill number is simply the `bills.id` primary key, which PostgreSQL
assigns atomically via its identity/serial column. Two simultaneous
"create bill" requests can never receive the same number, and the
counter survives refreshes, browser restarts, and server restarts,
because it lives in the database, not in the browser or in Python code.

**Important caveat:** this guarantees *uniqueness*, not legally
mandated *gap-free* sequential numbering (e.g. a failed/rolled-back
insert can still consume an id). If your jurisdiction requires
strictly gap-free invoice numbers, treat that as a separate
business/accounting requirement to confirm with an accountant — it is
not something a database identity column alone can promise.

Editing a bill (`PUT /api/bills/{id}`) never changes its number.

## 7. Bill persistence

`GET /api/bills` / `GET /api/bills/{id}` are the only source of truth
for the Bill Records screen — there is no more in-memory
`billRecords` array. Records survive page refresh, browser restart,
computer restart, and server restart, because everything lives in
PostgreSQL.

## 8. Mobile responsiveness

* Existing breakpoints (`900px` sidebar collapse, `700px` bill-preview
  stacking) are preserved.
* Added: touch-friendly buttons (min 40–44px tap height), a responsive
  filter bar for Bill Records, and a classic responsive-table pattern
  that turns the Bill Records table into stacked cards under `760px`
  (each cell gets a `data-label` shown via CSS `::before`).
* The **printable bill** (`#billPreview`) keeps its original fixed,
  professional layout — the printable table only gets a horizontal
  scroll wrapper on narrow screens so the surrounding app UI doesn't
  overflow; the print/PDF output itself is untouched.

## 9. Run it locally

### Backend

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt

cp .env.example .env
# edit .env: set DATABASE_URL, SECRET_KEY, ADMIN_PASSWORD, FRONTEND_ORIGIN

# create the PostgreSQL database first, e.g.:
#   createdb jewellery_bills
# (tables are created automatically on first startup)

uvicorn app.main:app --reload --port 8000
```

Check `http://localhost:8000/api/health` → `{"status": "ok"}`.

### Frontend

The frontend is a static file — serve it with any static server, e.g.:

```bash
cd frontend
python3 -m http.server 5500
```

Open `http://localhost:5500`. By default the page calls the API at
`http://localhost:8000`; override with `?api=http://your-api-host:8000`
in the URL if needed, or edit the `API_BASE` constant near the top of
the `<script>` block in `index.html`.

Make sure `FRONTEND_ORIGIN` in the backend `.env` exactly matches the
origin you're serving the frontend from (scheme + host + port).

## 10. Environment variables (backend/.env)

| Variable | Purpose |
|---|---|
| `DATABASE_URL` | PostgreSQL connection string (`postgresql+psycopg2://user:pass@host:port/db`) |
| `SECRET_KEY` | Random secret, reserved for future token/signing needs |
| `ADMIN_PASSWORD` | Plaintext password used **once** to seed the admin account (hashed on first boot) |
| `FRONTEND_ORIGIN` | Exact frontend origin, used for CORS |
| `COOKIE_SECURE` | `true` in production (HTTPS only); `false` only for local plain-HTTP dev |
| `SESSION_TTL_HOURS` | How long a login session lasts (default 12) |

Never commit `.env` — only `.env.example` is tracked (see `.gitignore`).

## 11. Testing checklist

**Authentication**
- [ ] Login works with the correct password
- [ ] Wrong password is rejected (`401`)
- [ ] Repeated wrong attempts are rate-limited (`429`)
- [ ] Unauthenticated requests to `/api/bills*` return `401`
- [ ] Logout clears the session (subsequent requests `401`)
- [ ] No password appears anywhere in the frontend source

**Bills**
- [ ] Create a bill → server assigns the next bill number
- [ ] Two bills created back-to-back get sequential, unique numbers
- [ ] Edit a bill → number stays the same
- [ ] Delete a bill → confirmation prompt, items removed too
- [ ] Records survive a page refresh / browser restart / server restart

**Calculations** (server-side, re-verified independently of the frontend)
- [ ] Net Weight = Gross − Less
- [ ] Item Total = Net Weight × Rate + Labour
- [ ] Subtotal = sum of item totals
- [ ] CGST / SGST computed on subtotal
- [ ] Grand Total = Subtotal + CGST + SGST
- [ ] Due = Grand Total − (Received Online + Received Cash)
- [ ] Negative weights / rates / GST are rejected with a clear error

**UI**
- [ ] Desktop / laptop / tablet layouts
- [ ] 375px, 390px, 414px mobile widths — no horizontal page overflow
- [ ] Touch-friendly buttons
- [ ] Records readable as cards on mobile
- [ ] Search/filter by bill number, customer name, mobile

**Printing**
- [ ] Print works and looks professional
- [ ] PDF download works
- [ ] Stamp/signature image persists after saving and reloading a bill

> The backend's automated tests above (auth, CRUD, validation, rate
> limiting, cascading delete) were run against this codebase with
> `pytest`/`TestClient` during development and pass. Running the app
> end-to-end in a real browser against a real PostgreSQL instance,
> and testing on physical phones, is still recommended before going
> live — that part could not be executed in this authoring environment.

## 12. Deployment (free/low-cost friendly)

The app has no hardcoded `localhost` in application logic — everything
comes from `DATABASE_URL` / `FRONTEND_ORIGIN` / `SECRET_KEY`, so it can
be deployed as:

```
Static frontend (e.g. Netlify, Vercel, GitHub Pages, Cloudflare Pages)
        ↓  HTTPS
Backend API (e.g. Render, Railway, Fly.io — any host that runs
             `uvicorn app.main:app`)
        ↓
Managed PostgreSQL (e.g. Render/Railway/Neon/Supabase free tier)
```

Steps:
1. Provision a PostgreSQL database with your chosen provider; copy its
   connection string into `DATABASE_URL`.
2. Deploy the `backend/` folder to your chosen host, set the
   environment variables from `.env.example` (including a strong,
   unique `SECRET_KEY` and `ADMIN_PASSWORD`), and set `COOKIE_SECURE=true`.
3. Deploy `frontend/index.html` as a static site; set its `API_BASE`
   (via the `?api=` query param or by editing the constant) to your
   deployed backend's HTTPS URL.
4. Set `FRONTEND_ORIGIN` on the backend to the exact deployed frontend
   URL, and re-deploy the backend.
5. Since free tiers change frequently, verify current pricing/limits
   with each provider before committing to one.

## Notes on scope

This implementation covers everything in the upgrade brief: PostgreSQL
persistence, backend-assigned atomic bill numbering, server-side
recalculation and validation of all financial values, Argon2-hashed
single-admin auth with HttpOnly session cookies and CORS restricted to
one origin, cascading delete via a real FK, mobile-responsive CSS that
leaves the print layout untouched, friendly error/loading states, and
a documented deployment path. What this authoring environment could
not do is run a live PostgreSQL server or a real browser end-to-end
against it (network access here is restricted to package registries) —
the backend logic was instead verified with FastAPI's `TestClient`
(login, rate limiting, create/list/search/edit/delete, cascading
delete, validation rejection, 401 handling all pass). Please run
through the checklist in section 11 yourself against a real Postgres +
browser before relying on this for live customer billing.
