-- =====================================================================
-- MUJ Mess - queries to run in MySQL Workbench during the demo.
-- Put the cursor inside a query and press Ctrl+Enter (Cmd+Enter on Mac)
-- to run just that one. Re-run it after each action on the website.
-- =====================================================================
USE mess;
SET time_zone = '+05:30';   -- show times in India time (the cloud server runs on UTC)

-- 1. LIVE FEED: every enrolment, login, booking, pause, serve and donation (written by triggers)
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
SELECT s.reg_no, s.full_name, p.from_date, p.to_date
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

-- 8. THE ROSTER: every student, joined to programme and hostel, with their mess use
SELECT reg_no, full_name, programme, year_of_study, hostel, room_no, last_login, meals_booked, meals_eaten
FROM v_student_directory ORDER BY last_login DESC, reg_no LIMIT 30;

-- 9. Logins (the SMS code is checked by Firebase; we keep who logged in and when)
SELECT l.at, s.reg_no, s.full_name FROM logins l JOIN students s ON s.id = l.student_id
ORDER BY l.id DESC LIMIT 20;

-- 10. Which hostel eats where today
SELECT hostel, SUM(mess = 'BluDove') AS dove_rows, SUM(booked) AS plates
FROM v_hostel_split WHERE meal_date = CURDATE() GROUP BY hostel ORDER BY plates DESC;

-- 11. Students per programme and year (GROUP BY ... WITH ROLLUP adds subtotals)
SELECT p.code AS programme, s.year_of_study, COUNT(*) AS students
FROM students s JOIN programmes p ON p.id = s.programme_id
GROUP BY p.code, s.year_of_study WITH ROLLUP;

-- 12. Who books but never turns up? (LEFT JOIN + HAVING)
SELECT s.reg_no, s.full_name, COUNT(b.id) AS booked, COUNT(a.id) AS eaten
FROM students s
JOIN bookings b       ON b.student_id = s.id AND b.status = 'booked' AND b.meal_date <= CURDATE()
LEFT JOIN attendance a ON a.student_id = b.student_id AND a.meal_date = b.meal_date AND a.slot_id = b.slot_id
GROUP BY s.id, s.reg_no, s.full_name
HAVING booked >= 2 AND eaten = 0
ORDER BY booked DESC LIMIT 15;

-- ---------------------------------------------------------------------
-- Show the database enforcing rules on its own (try these live):
-- ---------------------------------------------------------------------

-- a) Add a student to the roster. Put YOUR name and number here, run it, then log in on the website with it.
--    Watch query 1: the ENROL row appears, written by trg_student_enrol.
--    hostel_id: 1-12 = B1-B12 (boys), 13-22 = G1-G10 (girls).
-- INSERT INTO students (reg_no, full_name, gender, phone, email, programme_id, year_of_study, hostel_id, room_no, joined_on)
-- VALUES ('230100999', 'Your Name', 'F', '9876501234', 'you@muj.manipal.edu', 1, 3, 13, '214', '2023-07-24');

-- a2) The database refuses bad data by itself. Run each one and read the error:
--   a man in a girls' hostel (G1)  ->  trigger trg_student_check_ins: "This hostel is for the other gender"
-- INSERT INTO students (reg_no, full_name, gender, phone, email, programme_id, year_of_study, hostel_id, room_no, joined_on)
-- VALUES ('230100998', 'Wrong Hostel', 'M', '9876501235', 'w@muj.manipal.edu', 1, 1, 13, '101', '2023-07-24');
--   year 6 of a 4-year B.Tech  ->  same trigger: "Year of study is outside this programme"
-- INSERT INTO students (reg_no, full_name, gender, phone, email, programme_id, year_of_study, hostel_id, room_no, joined_on)
-- VALUES ('230100997', 'Wrong Year', 'M', '9876501236', 'y@muj.manipal.edu', 1, 6, 1, '101', '2023-07-24');
--   a 5-digit phone  ->  CHECK constraint chk_phone
-- INSERT INTO students (reg_no, full_name, gender, phone, email, programme_id, year_of_study, hostel_id, room_no, joined_on)
-- VALUES ('230100996', 'Bad Phone', 'M', '12345', 'p@muj.manipal.edu', 1, 1, 1, '101', '2023-07-24');

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
