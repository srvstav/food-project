"""
Fill the database with one realistic day, so every view and dashboard has numbers to show.

  python demo_data.py          use backend/.env         (this laptop's MySQL)
  python demo_data.py cloud    use backend/.env.render  (the shared cloud MySQL)

Adds 80 sample students (phones 70000 00001...), today's bookings for all 4 meals,
a few students on pause, attendance for breakfast and lunch, then runs sp_close_meal
for those two meals so donations appear. Safe to run more than once.
"""
from __future__ import annotations

import random
import sys
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import pymysql
from dotenv import dotenv_values

ROOT = Path(__file__).resolve().parent
env_file = ROOT / "backend" / (".env.render" if len(sys.argv) > 1 and sys.argv[1] == "cloud" else ".env")
if not env_file.exists():
    sys.exit(f"{env_file.name} not found. Run setup first.")
env = dotenv_values(env_file)

ssl = None
if env.get("DB_SSL_CA_PEM"):
    ca = ROOT / "backend" / "ca.pem"
    if not ca.exists():
        ca.write_text(env["DB_SSL_CA_PEM"].replace("\\n", "\n"), encoding="utf-8")
    ssl = {"ca": str(ca)}

conn = pymysql.connect(host=env["DB_HOST"], port=int(env["DB_PORT"]), user=env["DB_USER"],
                       password=env["DB_PASSWORD"], database=env["DB_NAME"], ssl=ssl,
                       charset="utf8mb4", autocommit=False, init_command="SET time_zone = '+05:30'")
today = datetime.now(ZoneInfo("Asia/Kolkata")).date()
rng = random.Random(str(today))  # same "day" if run twice on the same date
phones = [f"70000{n:05d}" for n in range(1, 81)]

# Share of students picking BluDove per meal (the rest pick BluSpring), and share skipping.
TASTE = {1: (0.55, 0.12), 2: (0.40, 0.08), 3: (0.62, 0.30), 4: (0.47, 0.10)}

with conn, conn.cursor() as cur:
    cur.executemany("INSERT IGNORE INTO students (phone) VALUES (%s)", [(p,) for p in phones])
    cur.execute("SELECT id, phone FROM students WHERE phone IN (" + ",".join(["%s"] * len(phones)) + ")", phones)
    ids = [row[0] for row in cur.fetchall()]

    away = ids[:5]           # five students went home for the weekend
    eating = ids[5:]
    for sid in eating:
        for slot, (dove, skip) in TASTE.items():
            r = rng.random()
            mess, status = (None, "skipped") if r < skip else ((1 if rng.random() < dove else 2), "booked")
            cur.execute(
                "INSERT INTO bookings (student_id, meal_date, slot_id, mess_id, status) VALUES (%s,%s,%s,%s,%s) AS n "
                "ON DUPLICATE KEY UPDATE mess_id = n.mess_id, status = n.status",
                (sid, today, slot, mess, status))
    conn.commit()

    for sid in away:
        cur.execute("SELECT 1 FROM pauses WHERE student_id = %s AND ended_on IS NULL AND to_date >= %s", (sid, today))
        if not cur.fetchone():
            cur.execute("CALL sp_pause_mess(%s, %s, %s)", (sid, today, today + timedelta(days=3)))

    # Breakfast and lunch are over: about 85% of bookers came, plus a few walk-ins.
    for slot in (1, 2):
        cur.execute("SELECT student_id, mess_id FROM bookings WHERE meal_date = %s AND slot_id = %s AND status = 'booked'",
                    (today, slot))
        for sid, mess in cur.fetchall():
            if rng.random() < 0.85:
                cur.execute("INSERT IGNORE INTO attendance (student_id, meal_date, slot_id, mess_id) VALUES (%s,%s,%s,%s)",
                            (sid, today, slot, mess))
        cur.execute("SELECT student_id FROM bookings WHERE meal_date = %s AND slot_id = %s AND status = 'skipped'",
                    (today, slot))
        for (sid,) in cur.fetchall()[:3]:  # changed their mind and walked in anyway
            cur.execute("INSERT IGNORE INTO attendance (student_id, meal_date, slot_id, mess_id) VALUES (%s,%s,%s,%s)",
                        (sid, today, slot, rng.choice((1, 2))))
        conn.commit()
        cur.execute("CALL sp_close_meal(%s, %s)", (today, slot))
    conn.commit()

    cur.execute("SELECT meal, mess, booked, cooked, served, no_shows, walk_ins, donate FROM v_meal_summary "
                "WHERE meal_date = %s ORDER BY slot_id, mess_id", (today,))
    print(f"Demo day loaded for {today}:")
    print(f"  {'meal':<10}{'mess':<11}{'booked':>7}{'cooked':>7}{'served':>7}{'no-show':>8}{'walk-in':>8}{'donate':>7}")
    for r in cur.fetchall():
        print(f"  {r[0]:<10}{r[1]:<11}{r[2]:>7}{r[3]:>7}{r[4]:>7}{r[5]:>8}{r[6]:>8}{r[7]:>7}")
