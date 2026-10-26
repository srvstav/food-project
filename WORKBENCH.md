# Showing it in MySQL Workbench (Windows)

This is the part the examiner marks. Everything below happens inside MySQL Workbench.

## 1. Connect (once per laptop, 2 minutes)

**If the project is on the cloud database** (the website at srvstav.github.io/mess uses it):

1. Open Workbench → click **⊕** next to *MySQL Connections*.
2. Fill in from `CLOUD_DETAILS.txt` (the group gets it from whoever ran `setup_cloud.bat`):
   - Connection Name: `MUJ Mess (cloud)`
   - Hostname, Port, Username: as written in the file
   - Password: **Store in Vault…** → paste it
3. **SSL** tab → *Use SSL*: **Require** → *SSL CA File*: pick `ca.pem` (sent along with the file).
4. **Test Connection** → OK → OK. Double-click the new tile to open it.

**If you run it on the laptop itself** (works without internet): run `setup.bat` then `start.bat` (README, section A).
In Workbench use Hostname `127.0.0.1`, Port `3306`, Username `root` and the root password from the MySQL install.

## 2. What to show, in this order (about 5 minutes)

Open **File → Open SQL Script → `db\demo_queries.sql`**. Put the cursor inside one query and press **Ctrl + Enter** to run only that query.

| Show | How | What to say |
| --- | --- | --- |
| **The schema** | Left sidebar → *Schemas* → `mess` → open Tables, Views, Stored Procedures, Functions | 14 tables in 3NF, 7 views, 4 procedures, 1 function, 12 triggers |
| **ER diagram** | **Database → Reverse Engineer…** → your connection → Next → tick `mess` → Next until **Execute**, then **Finish** | Every line is a foreign key. Students → programmes and hostels; bookings, attendance, pauses → students; donations → NGOs |
| **The roster** | Query 8 (`v_student_directory`) | 1,200 students joined to their programme and hostel, with last login and meals eaten |
| **Live data** | Book a meal on the website (phone), then run **query 1** | The BOOK row was written by a trigger, not by the website |
| **The kitchens' numbers** | Queries 3 and 4 | `cook_for = booked × 1.3`, worked out by a view; no-shows, walk-ins and donations after the meal |
| **The business side** | `SELECT * FROM v_mess_earnings WHERE meal_date = CURDATE() - INTERVAL 1 DAY;` | Each mess is paid per plate served and pays per plate cooked: profit, waste |
| **A trigger refusing bad data** | Query **a2**: a man in a girls' hostel | Error 1644: "This hostel is for the other gender", raised by `trg_student_check_ins` |
| **A CHECK constraint** | Last insert in **a2** (phone `12345`) | Refused by `chk_phone` (error 3819) |
| **A stored procedure** | `CALL sp_close_meal(CURDATE(), 1);` then query 5 | A cursor gives leftovers to the NGO that has received the least so far, in one transaction |
| **Add yourself, then log in** | Query **a** with your own name and number, run it, then log in on the website with that number | The ENROL row appears in query 1; the website greets you by name |

Tip: Workbench doesn't refresh on its own. Press Ctrl + Enter again after each action on the website.
Keep `dashboard.html` open beside it for a view that refreshes every 2 seconds.

## 3. Make it move during the presentation

On the laptop that set the project up, run `python demo_data.py cloud live` (or `python demo_data.py live` for the
offline setup). It makes a booking, a mess switch or a serve every second or two. Re-run query 1 in Workbench and new rows are there each time.

## If something goes wrong

| Problem | Fix |
| --- | --- |
| Test Connection fails on the cloud | Check the SSL tab says **Require** and points at `ca.pem`. The free cloud database may be sleeping: open the website once, wait a minute, retry |
| `Access denied` | Wrong password. Copy it again from `CLOUD_DETAILS.txt` (no spaces) |
| Reverse Engineer shows no tables | On the "Select Schemas" page, tick `mess` |
| Queries show yesterday's data | Run `demo_data.bat` / `demo_cloud.bat` the morning of the demo |
