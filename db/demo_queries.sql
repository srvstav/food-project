-- =====================================================================
-- MUJ Mess - queries to run in MySQL Workbench during the demo.
-- Put the cursor inside a query and press Ctrl+Enter (Cmd+Enter on Mac)
-- to run just that one. Re-run it after each action on the website.
-- =====================================================================
USE mess;
SET time_zone = '+05:30';   -- show times in India time (the cloud server runs on UTC)

-- 1. LIVE FEED: every signup, login, booking, pause, serve and donation (written by triggers)
SELECT id, at, event, detail FROM activity_log ORDER BY id DESC LIMIT 30;

-- 2. Every student's choice, newest first
SELECT * FROM v_live_bookings LIMIT 30;

-- 3. FORECAST: what each mess cooks today = booked + 30% buffer
SELECT mess, meal, booked, cook_for
FROM v_daily_forecast
WHERE meal_date = CURDATE()
ORDER BY slot_id, mess_id;

-- 4. AFTER THE MEAL: served, no-shows, walk-ins, food left to donate
SELECT meal, mess, booked, cooked, served, no_shows, walk_ins, buffer_left, donate
FROM v_meal_summary
WHERE meal_date = CURDATE()
ORDER BY slot_id, mess_id;

-- 5. Donations and NGO totals
SELECT d.meal_date, ms.name AS meal, m.name AS mess, n.name AS ngo, d.portions
FROM donations d
JOIN meal_slots ms ON ms.id = d.slot_id
JOIN messes m      ON m.id = d.mess_id
JOIN ngos n        ON n.id = d.ngo_id
ORDER BY d.id DESC;
SELECT * FROM v_ngo_totals;

-- 6. Students away from campus right now
SELECT s.phone, p.from_date, p.to_date
FROM pauses p JOIN students s ON s.id = p.student_id
WHERE p.ended_on IS NULL AND CURDATE() BETWEEN p.from_date AND p.to_date;

-- 7. Which mess is more popular, per meal (GROUP BY + conditional aggregation)
SELECT ms.name AS meal,
       SUM(b.mess_id = 1) AS bludove,
       SUM(b.mess_id = 2) AS bluspring,
       SUM(b.status = 'skipped') AS skipped
FROM bookings b JOIN meal_slots ms ON ms.id = b.slot_id
WHERE b.meal_date = CURDATE()
GROUP BY ms.id, ms.name ORDER BY ms.id;

-- 8. OTPs issued (only a keyed hash is stored, never the code itself)
SELECT id, phone, LEFT(code_hash, 12) AS hash_prefix, expires_at, attempts, used_at
FROM otp_codes ORDER BY id DESC LIMIT 10;

-- ---------------------------------------------------------------------
-- Show the database enforcing rules on its own (try these live):
-- ---------------------------------------------------------------------

-- a) CHECK constraint: an invalid phone number is rejected
-- INSERT INTO students (phone) VALUES ('12345');

-- b) UNIQUE key: a student can't hold two choices for the same meal
--    (the website updates the row instead - see ON DUPLICATE KEY UPDATE in repo.py)

-- c) Trigger: booking while paused is refused with "Your mess is paused for this date"
--    (pause on the website, then try to book that day)

-- d) Stored procedure: close a meal and hand leftovers to NGOs
-- CALL sp_close_meal(CURDATE(), 1);

-- e) Look at the objects
SHOW FULL TABLES;
SHOW TRIGGERS;
SHOW PROCEDURE STATUS WHERE Db = 'mess';
