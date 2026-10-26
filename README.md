# Food Project: MUJ Mess (Java)

Students pay one annual fee and eat at two messes, **BluDove** and **BluSpring**. They book where they'll eat each meal (breakfast, lunch, hi-tea, dinner). Each kitchen cooks for the people who booked, plus 30%. Staff mark who was served, and leftover food goes to NGOs.

**An Object-Oriented Programming in Java project.** The backend is plain Java 17 with no frameworks, so every OOP idea shows up in our own code. Every place an idea is used has a comment that starts with `// OOP:`.

**Studying for the viva? Read [OOP_GUIDE.md](OOP_GUIDE.md).** It covers every concept, the file it's in, how one request moves through the system, and the questions an examiner is likely to ask.

```
 Browser (docs/: HTML + JS)  ──HTTP/JSON──►  Java backend (backend/)  ──JDBC──►  MySQL 8 (db/)
  student site, staff counter,               controller → service → repository     14 tables, 12 triggers,
  live dashboard                                                                    4 procedures, 7 views
```

| Page | What it is |
| --- | --- |
| http://localhost:8000 | Student site: log in with a code shown on screen, book meals, pause when going home |
| http://localhost:8000/staff.html | Mess counter: mark students served, close a meal so leftovers go to NGOs (needs the staff PIN) |
| http://localhost:8000/dashboard.html | Live board: each mess's profit, waste and no-shows over 7 days, tomorrow's plan, live MySQL feed |

## Run it (Windows, about 10 minutes the first time)

1. **Install once:**
   - **JDK 17 or newer**: https://adoptium.net (Temurin). Tick "Set JAVA_HOME" and "Add to PATH".
   - **MySQL Server 8 + Workbench**: https://dev.mysql.com/downloads/installer/ → Custom → MySQL Server + MySQL Workbench. Remember the root password.
   - **Python 3.12+** (only to build the database and load demo data): https://www.python.org/downloads/. Tick "Add python.exe to PATH".
2. **Download this repo:** Code → Download ZIP, then unzip it (for example to `C:\food-project`).
3. Double-click **`setup.bat`**. Press Enter 3 times, then type the MySQL root password. It builds the `mess` database and prints a **Staff PIN**. Write the PIN down.
4. Double-click **`demo.bat`** (optional, recommended). It fills a realistic day: about 700 students' bookings, serves and donations.
5. Double-click **`start.bat`**. The first run downloads Maven and builds the Java code (a few minutes). Then the site opens at http://localhost:8000. Keep the black window open.

macOS/Linux: `python3 setup.py local`, then `./start.sh`.

**Changed a `.java` file?** Run **`build.bat`** (it rebuilds and runs the unit tests), then `start.bat` again.

**No Python?** In MySQL Workbench open and run `db/mess_complete.sql` (see [WORKBENCH.md](WORKBENCH.md)). Then copy `backend/.env.example` to `backend/.env` and fill in your MySQL user and password.

**During the demo:** `python demo_data.py live` keeps making bookings and serves every second or two, so the dashboard moves. Ctrl+C stops it. `reset.bat` wipes the database and rebuilds it.

## Try it

1. Open the student site, type any 10-digit number starting with 6–9, and tap Send code. The code appears on screen (demo mode, no SMS). Type it to log in.
2. Book lunch at BluDove. Then pause your mess for tomorrow and try booking tomorrow: MySQL's trigger refuses it, and Java turns that into a clear message.
3. Open the staff counter, enter the PIN, and serve your number. Serve it again: "Already served this meal today".
4. Close a meal: leftover portions go to the NGO that has received the least so far.
5. Watch the dashboard update every 2 seconds.

## How the code is organised

```
backend/src/main/java/com/muj/mess/
  Main.java                 start here: creates every object and wires them together
  config/AppConfig.java     settings (record, immutable)
  db/Database.java          opens MySQL connections, runs work in a transaction
  db/SqlWork.java           functional interface: "some work to do on a connection"
  model/                    data: Student, Booking (records), MealStatus (enum),
                            Validatable (interface), Requests (the JSON bodies, each validates itself)
  repository/               all SQL. BaseRepository (abstract) ← StudentRepository, MenuRepository,
                            BookingRepository, MealRepository, DashboardRepository
  service/                  business rules: AuthService, TokenService, RateLimiter,
                            StudentService, StaffService, DashboardService
  web/                      the HTTP server: ApiServer, Router, ApiRequest, Endpoint, Controller,
                            ApiException (abstract) ← BadRequest, Unauthorized, Forbidden, NotFound …
  web/controller/           AuthController, StudentController, StaffController, DashboardController
backend/src/test/java/      JUnit tests
db/                         schema.sql (tables, triggers, procedures, views), seed.sql, students.csv
docs/                       the website (HTML/CSS/JS)
```

Find every OOP comment: `findstr /s /n "OOP:" backend\src\main\java\*.java` (Windows) or `grep -rn "OOP:" backend/src` (macOS/Linux).

## API

| Method | Path | Who | What |
| --- | --- | --- | --- |
| GET | `/health` | anyone | API and database are up |
| POST | `/auth/check` | anyone | make a login code for a phone (rate-limited: 10 per 10 min per IP) |
| POST | `/auth/demo-verify` | anyone | check the code, get a session token |
| GET | `/me` | student | my profile |
| GET | `/menu` | anyone | dishes per meal per mess |
| GET | `/bookings/me?meal_date=` | student | my bookings for a day |
| POST | `/bookings` | student | book (`mess_id`) or skip (`mess_id: null`) a meal |
| GET / POST | `/pause/me`, `/pause` | student | see / add a pause (stored procedure `sp_pause_mess`) |
| POST | `/resume` | student | come back early (`sp_resume_mess`) |
| GET | `/staff/check` | staff PIN | check the PIN |
| POST | `/staff/serve` | staff PIN | mark a student served |
| POST | `/staff/close-meal` | staff PIN | give leftovers to NGOs (`sp_close_meal`) |
| GET | `/stats/today`, `/admin/live` | anyone | dashboard data (phone numbers masked) |

## Troubleshooting

| Problem | Fix |
| --- | --- |
| `'java' is not recognized` | Install the JDK (step 1), then open a new window |
| `Missing setting DB_USER` | Run `setup.bat` first; it writes `backend/.env` |
| "Database is unavailable" | MySQL isn't running: `Win + R` → `services.msc` → start **MySQL80** |
| Port 8000 in use | Close the other server window, or run `set PORT=8001` and then `start.bat` in the same window |
| Changed Java code but nothing changed | Run `build.bat`, then restart `start.bat` |
