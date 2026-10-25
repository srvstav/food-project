# MUJ Mess

One annual fee and two messes (**BluDove** and **BluSpring**). Students book where they'll eat for every meal: breakfast, lunch, hi-tea and dinner. Each kitchen cooks for the people who booked, plus 30%. Staff mark who was served, and leftovers go to NGOs.

An RDBMS project: **MySQL 8** (11 tables, 10 triggers, 3 stored procedures, 4 views) + **Python FastAPI** + a plain HTML/CSS/JS website.

| Page | What it is |
| --- | --- |
| `index.html` | Student site: log in with phone + OTP, book meals, pause when going home |
| `staff.html` | Mess counter: mark students served, close a meal so leftovers go to NGOs |
| `dashboard.html` | Live board: everything happening in MySQL, refreshing every 2 seconds |
| `project.html` | **How it's built**: ER diagram, normalization, triggers, demo plan, viva answers |

```
 Website (GitHub Pages)  ──HTTPS──►  API (FastAPI on Render)  ──TLS──►  MySQL (Aiven)  ◄──  Workbench
      docs/                               backend/                          db/
 Offline mode: start.bat runs the API + website on one laptop against that laptop's MySQL.
```

---

## A. Run it on a Windows laptop (offline, about 10 minutes)

**1. Install once**

- **MySQL Server 8.0 or newer + MySQL Workbench**: https://dev.mysql.com/downloads/installer/ → *MySQL Installer for Windows* → choose **Custom** → add *MySQL Server* and *MySQL Workbench*. Remember the **root password** you set during the install.
  - Already have Workbench? Check the server too: press `Win + R`, type `services.msc`, and look for **MySQL80** (or MySQL84 / MySQL). It should say *Running*.
- **Python 3.12 or 3.13**: https://www.python.org/downloads/. On the first installer screen, tick **"Add python.exe to PATH"**.

**2. Get the project.** On GitHub press **Code → Download ZIP**, then unzip it somewhere simple, like `C:\mess`. Or use `git clone`.

**3. Double-click `setup.bat`.** It installs the Python packages, then asks for the MySQL details:

```
Host [127.0.0.1]:            ← press Enter
Port [3306]:                 ← press Enter
Admin user [root]:           ← press Enter
Password for root:           ← type your MySQL root password (nothing shows while typing; that's normal)
```

It then builds the `mess` database and prints a **Staff PIN**. Write the PIN down.

**4. Double-click `start.bat`.** Keep that black window open. The browser opens http://127.0.0.1:8000.

| URL | |
| --- | --- |
| http://127.0.0.1:8000 | student site |
| http://127.0.0.1:8000/dashboard.html | live board |
| http://127.0.0.1:8000/staff.html | staff counter (needs the PIN) |
| http://127.0.0.1:8000/project.html | how it's built |
| http://127.0.0.1:8000/docs | interactive API docs (Swagger) |

**5. (Optional) Double-click `demo.bat`.** It loads a realistic day: 80 students, bookings, pauses, attendance and donations, so every table and view has data to show.

`reset.bat` wipes the database and rebuilds it from scratch.

## B. Watch it live in MySQL Workbench

1. Open Workbench, then click **⊕** next to *MySQL Connections*.
2. Connection name: `MUJ Mess (local)` · Hostname `127.0.0.1` · Port `3306` · Username `root`. Click **OK**, then open it and enter the root password.
3. **File → Open SQL Script →** `db\demo_queries.sql`.
4. Do something on the website (log in, book, pause). Then click inside query 1 and press **Ctrl + Enter**. The new rows appear: SIGNUP, LOGIN, BOOK, PAUSE…

   Workbench doesn't refresh on its own. Press Ctrl + Enter again after each action, and keep `dashboard.html` open beside it for a view that refreshes by itself.
5. **ER diagram:** **Database → Reverse Engineer… →** pick the connection → select schema `mess` → Next until **Finish**. Workbench draws all 11 tables and their foreign keys.

## C. Put it online for everyone (one person, once)

This makes the website work from any phone, and all three laptops' Workbench show the **same** live database.

**1. Cloud MySQL (Aiven, free)**
1. Sign up at https://console.aiven.io (the GitHub login is fine).
2. **Create service → MySQL → Free plan →** create it, and wait until it shows *Running*.
3. On the service page, copy the **Service URI**. In the project's `backend` folder, create a file named `.env.cloud` containing one line:
   ```
   DATABASE_URL=mysql://avnadmin:PASSWORD@HOST:PORT/defaultdb?ssl-mode=REQUIRED
   ```
4. Click **CA certificate → Download** and save it as `backend\ca.pem`.
5. Double-click `setup_cloud.bat`. It builds the database in the cloud and writes `backend\.env.render`.

   If it says the server *"will refuse to create triggers"*: in Aiven, open **Service settings → Advanced configuration**, turn on `log_bin_trust_function_creators` if it's listed, and run the command again.

**2. Cloud API (Render, free)**
1. Sign up at https://render.com with GitHub, and give it access to this repository.
2. Open https://dashboard.render.com/blueprint/new, pick this repository, then click **Apply**.
3. Render asks for the values marked *sync: false*. Copy each one from `backend\.env.render`.
4. When it shows **Live**, copy its URL (like `https://mess-api-xxxx.onrender.com`) and open `<URL>/health`. It should say `"status":"ok"`.

**3. Point the website at it**
1. In `docs/config.js`, set `window.MESS_CLOUD_API = "https://mess-api-xxxx.onrender.com";`
2. Commit and push. GitHub Pages serves the `docs/` folder: **Settings → Pages → Branch `main` / `docs`**.
3. The `keep-awake` GitHub Action pings the API every 10 minutes during the day, so it never takes 50 seconds to wake during the demo.

**4. Workbench → cloud database (every laptop)**
New connection: Hostname and Port from Aiven · Username `avnadmin` · Password from Aiven.
On the **SSL** tab, set *Use SSL* to **Require**, and *SSL CA File* to `ca.pem`. Then **Test Connection**.

## D. Morning of the demo

- [ ] Open `<cloud API>/health`. It should say ok (this also wakes the server).
- [ ] Double-click `demo_cloud.bat` (or `demo.bat` for the offline setup) so today has data.
- [ ] Phone: the student site · Projector: `dashboard.html` · Laptop: Workbench with `demo_queries.sql`.
- [ ] Backup: if the Wi-Fi fails, use `start.bat` on one laptop (section A). Everything works without internet.
- [ ] Read `project.html` sections 10 and 11: who says what, and the likely viva questions.

## Troubleshooting

| Problem | Fix |
| --- | --- |
| `Python is not installed` | Install Python, tick **Add to PATH**, then run `setup.bat` again |
| `Access denied for user 'root'` | Wrong MySQL root password. Use the one from the MySQL install |
| `Can't connect to MySQL` | `services.msc` → start **MySQL80** |
| `start.bat` says *address already in use* | It's already running in another window. Close that window first |
| Website says *Can't reach the mess server* | Local: is the `start.bat` window open? Cloud: open `<API>/health` and wait up to a minute |
| Workbench shows old rows | Press **Ctrl + Enter** to run the query again |
| Want to start clean | `reset.bat` (local) or `setup_cloud.bat` (cloud) |

## How it's organised

```
db/schema.sql         tables, constraints, triggers, procedures, views
db/seed.sql           2 messes, 4 meals, menus, 3 NGOs
db/demo_queries.sql   open in Workbench during the demo
backend/main.py       API endpoints (controller)
backend/repo.py       every SQL statement, all parameterized (repository)
backend/auth.py       OTP login, signed tokens, staff PIN
backend/tests/        18 automated tests: run  backend\.venv\Scripts\python -m pytest -q backend\tests
docs/                 the website (student, staff, dashboard, project pages)
setup.py              builds the database (local or cloud), used by setup.bat
demo_data.py          loads a realistic day, used by demo.bat
```

**Design decisions**
- **Raw SQL, no ORM**, so every query, trigger and view can be seen and explained. All queries are parameterized.
- **The OTP is shown on screen (demo mode).** Sending SMS in India needs DLT registration. Codes are still random, expire in 5 minutes, work once, and are stored only as a keyed hash.
- **The app's database user is `mess_app`**, with SELECT, INSERT, UPDATE and EXECUTE only. It has no DELETE, DROP or ALTER.
- **India time everywhere.** Cloud servers run on UTC, so the API and every database session use `+05:30`.
- **Donation rule:** leftover = unused 30% buffer + 50% of the no-shows' portions, capped at what's actually left. It's assigned to the NGO that has received the least so far.
