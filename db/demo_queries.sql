-- Open in MySQL Workbench. Put the cursor on a query and press Ctrl/Cmd+Enter to re-run it.
USE mess;

-- 1. Live feed: every login and booking, newest first (filled by triggers)
SELECT id, at, event, detail FROM activity_log ORDER BY id DESC LIMIT 30;

-- 2. Every student's choice, newest first
SELECT * FROM v_live_bookings LIMIT 30;

-- 3. What each mess should cook today (booked + 30%)
SELECT mess, meal, booked, cook_for
FROM v_daily_forecast
WHERE meal_date = CURDATE()
ORDER BY mess, slot_order;

-- 4. Students
SELECT id, phone, created_at, last_login_at FROM students ORDER BY id DESC;

-- 5. OTPs issued (hashes only — the code itself is never stored)
SELECT id, phone, LEFT(code_hash, 12) AS hash_prefix, expires_at, attempts, used_at
FROM otp_codes ORDER BY id DESC LIMIT 10;
