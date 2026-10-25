# MUJ Mess

One annual fee, two messes (BluDove and BluSpring). Students log in with their phone number and pick a mess for each meal of the day: breakfast, lunch, hi-tea and dinner. Each mess cooks for the students who booked, plus 30%.

```
github.io page  ──https──►  Cloudflare tunnel  ──►  FastAPI (laptop)  ──►  MySQL  ◄── Workbench
   docs/                                          backend/                db/
```

GitHub Pages only serves static files, so the API and the database run on the laptop. The tunnel gives the API a public https URL.

## Run it

```bash
brew install mysql cloudflared && brew services start mysql
./db/setup.sh                 # builds DB `mess`, seeds menus, writes backend/.env (random password)
./run.sh                      # API on http://127.0.0.1:8000, live dashboard at /admin
cloudflared tunnel --url http://127.0.0.1:8000   # prints https://<random>.trycloudflare.com
```

Open the site once with the tunnel URL. The site remembers it after that:

```
https://srvstav.github.io/mess/?api=https://<random>.trycloudflare.com
```

## Watch it live in MySQL Workbench

1. New connection: `127.0.0.1:3306`, user `root` (no password on a fresh Homebrew install).
2. Open `db/demo_queries.sql`.
3. Log in on the site, then book a meal. Put the cursor on query 1 and press Cmd+Enter to see the new rows.

Workbench doesn't refresh on its own. `http://127.0.0.1:8000/admin` shows the same data and refreshes every 2 seconds. Put it next to Workbench.

## What's in the database

| Object | Kind | Purpose |
| --- | --- | --- |
| `messes`, `meal_slots`, `menu_items` | tables | the two messes, 4 meals, sample dishes |
| `students` | table | one row per phone number (checked by a regex CHECK) |
| `otp_codes` | table | keyed hash of each OTP, expiry, attempt count |
| `bookings` | table | one choice per student, date and meal (UNIQUE key); `skipped` = not counted |
| `activity_log` | table | live feed, written **only by triggers** |
| `trg_student_new`, `trg_student_login`, `trg_booking_new`, `trg_booking_change` | triggers | log signup, login, book, skip and change |
| `v_live_bookings` | view | readable list of every choice |
| `v_daily_forecast` | view | `booked` and `cook_for = CEIL(booked × 1.3)` per mess and meal |

## Tests

```bash
uv pip install -p backend/.venv -r backend/requirements-dev.txt
cd backend && .venv/bin/pytest -q
```

The tests write to the real `mess` database. Run `./db/setup.sh` again before a demo to clear the test data, then restart `./run.sh`, because setup makes a new password.

## Decisions

- **Raw SQL, no ORM.** It's an RDBMS project, so the queries, triggers and views should be visible. Every query uses parameters (`repo.py`).
- **The OTP is shown on the page (`OTP_MODE=dev`).** Sending SMS in India needs DLT registration, which takes days. The code is still random, expires in 5 minutes, works once, allows 5 tries and is stored only as a keyed hash.
- **The app uses a least-privilege DB user.** `mess_app` can only SELECT, INSERT and UPDATE. It can't DELETE or change the schema.
- **Cloudflare quick tunnel.** It's free, needs no account and serves https, so the github.io page can call it. The URL changes on every restart, which is why the site has the `?api=` override.

## Not built yet

Pausing the mess while away, the donation share (leftover buffer + 50% of no-shows), real SMS, and the design pass.
