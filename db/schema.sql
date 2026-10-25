-- =====================================================================
-- MUJ Mess — one annual fee, eat at either mess, book every meal.
-- MySQL 8.0+. Run with:  python setup.py local   (or: setup.bat on Windows)
--
-- Tables (3NF):  messes, meal_slots, menu_items, students, otp_codes,
--                bookings, pauses, attendance, ngos, donations, activity_log
-- Triggers:      log every signup/login/booking/serve; block bookings while paused
-- Views:         v_live_bookings, v_daily_forecast, v_meal_summary, v_ngo_totals
-- Procedures:    sp_pause_mess, sp_resume_mess, sp_close_meal (transactions)
-- =====================================================================
DROP DATABASE IF EXISTS mess;
CREATE DATABASE mess CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci;
USE mess;

-- ---------- reference data ----------

CREATE TABLE messes (
  id   TINYINT UNSIGNED PRIMARY KEY,
  name VARCHAR(40) NOT NULL UNIQUE
);

CREATE TABLE meal_slots (
  id         TINYINT UNSIGNED PRIMARY KEY,
  code       VARCHAR(16) NOT NULL UNIQUE,
  name       VARCHAR(32) NOT NULL,
  starts_at  TIME NOT NULL,
  ends_at    TIME NOT NULL,
  CONSTRAINT chk_slot_time CHECK (ends_at > starts_at)
);

-- One row per dish. The same weekly menu is used every day in this demo.
CREATE TABLE menu_items (
  id       INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
  mess_id  TINYINT UNSIGNED NOT NULL,
  slot_id  TINYINT UNSIGNED NOT NULL,
  dish     VARCHAR(80) NOT NULL,
  UNIQUE KEY uq_dish (mess_id, slot_id, dish),
  FOREIGN KEY (mess_id) REFERENCES messes(id),
  FOREIGN KEY (slot_id) REFERENCES meal_slots(id)
);

CREATE TABLE ngos (
  id             SMALLINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
  name           VARCHAR(80) NOT NULL UNIQUE,
  area           VARCHAR(80) NOT NULL,
  contact_phone  CHAR(10) NOT NULL
);

-- ---------- people and login ----------

CREATE TABLE students (
  id             INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
  phone          CHAR(10) NOT NULL UNIQUE,
  created_at     DATETIME(3) NOT NULL DEFAULT CURRENT_TIMESTAMP(3),
  last_login_at  DATETIME(3) NULL,
  CONSTRAINT chk_phone CHECK (REGEXP_LIKE(phone, '^[6-9][0-9]{9}$'))
);

-- Only a keyed hash (HMAC-SHA256) of each OTP is stored, never the code itself.
CREATE TABLE otp_codes (
  id          INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
  phone       CHAR(10) NOT NULL,
  code_hash   CHAR(64) NOT NULL,
  expires_at  DATETIME(3) NOT NULL,
  attempts    TINYINT UNSIGNED NOT NULL DEFAULT 0,
  used_at     DATETIME(3) NULL,
  created_at  DATETIME(3) NOT NULL DEFAULT CURRENT_TIMESTAMP(3),
  INDEX idx_otp_phone (phone, created_at)
);

-- ---------- the core: one choice per student per day per meal ----------
-- booked  = eating at mess_id          (counted)
-- skipped = not eating this meal       (not counted)
-- paused  = away from campus           (not counted, set by sp_pause_mess)
CREATE TABLE bookings (
  id          INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
  student_id  INT UNSIGNED NOT NULL,
  meal_date   DATE NOT NULL,
  slot_id     TINYINT UNSIGNED NOT NULL,
  mess_id     TINYINT UNSIGNED NULL,
  status      ENUM('booked','skipped','paused') NOT NULL,
  created_at  DATETIME(3) NOT NULL DEFAULT CURRENT_TIMESTAMP(3),
  updated_at  DATETIME(3) NOT NULL DEFAULT CURRENT_TIMESTAMP(3) ON UPDATE CURRENT_TIMESTAMP(3),
  UNIQUE KEY uq_one_choice (student_id, meal_date, slot_id),
  INDEX idx_forecast (meal_date, slot_id, mess_id, status),
  FOREIGN KEY (student_id) REFERENCES students(id),
  FOREIGN KEY (slot_id)    REFERENCES meal_slots(id),
  FOREIGN KEY (mess_id)    REFERENCES messes(id),
  CONSTRAINT chk_status_mess CHECK ((status = 'booked') = (mess_id IS NOT NULL))
);

-- A student away from campus. ended_on is set when they come back early.
CREATE TABLE pauses (
  id          INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
  student_id  INT UNSIGNED NOT NULL,
  from_date   DATE NOT NULL,
  to_date     DATE NOT NULL,
  ended_on    DATE NULL,
  created_at  DATETIME(3) NOT NULL DEFAULT CURRENT_TIMESTAMP(3),
  INDEX idx_pause_student (student_id, from_date, to_date),
  FOREIGN KEY (student_id) REFERENCES students(id),
  CONSTRAINT chk_pause_range CHECK (to_date >= from_date)
);

-- Who actually ate. Staff record this at the counter.
-- A student with no booking at this mess is a walk-in (served from the 30% buffer).
CREATE TABLE attendance (
  id          INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
  student_id  INT UNSIGNED NOT NULL,
  meal_date   DATE NOT NULL,
  slot_id     TINYINT UNSIGNED NOT NULL,
  mess_id     TINYINT UNSIGNED NOT NULL,
  served_at   DATETIME(3) NOT NULL DEFAULT CURRENT_TIMESTAMP(3),
  UNIQUE KEY uq_served_once (student_id, meal_date, slot_id),
  INDEX idx_att_meal (meal_date, slot_id, mess_id),
  FOREIGN KEY (student_id) REFERENCES students(id),
  FOREIGN KEY (slot_id)    REFERENCES meal_slots(id),
  FOREIGN KEY (mess_id)    REFERENCES messes(id)
);

-- Food given away after a meal closes. One row per mess per meal.
CREATE TABLE donations (
  id          INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
  meal_date   DATE NOT NULL,
  slot_id     TINYINT UNSIGNED NOT NULL,
  mess_id     TINYINT UNSIGNED NOT NULL,
  ngo_id      SMALLINT UNSIGNED NOT NULL,
  portions    INT UNSIGNED NOT NULL,
  created_at  DATETIME(3) NOT NULL DEFAULT CURRENT_TIMESTAMP(3),
  UNIQUE KEY uq_one_donation (meal_date, slot_id, mess_id),
  FOREIGN KEY (slot_id) REFERENCES meal_slots(id),
  FOREIGN KEY (mess_id) REFERENCES messes(id),
  FOREIGN KEY (ngo_id)  REFERENCES ngos(id)
);

-- Filled only by triggers — the live feed to watch in Workbench.
CREATE TABLE activity_log (
  id          BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
  at          DATETIME(3) NOT NULL DEFAULT CURRENT_TIMESTAMP(3),
  event       VARCHAR(20) NOT NULL,
  student_id  INT UNSIGNED NULL,
  detail      VARCHAR(200) NOT NULL,
  INDEX idx_log_at (at)
);

-- =====================================================================
-- TRIGGERS
-- =====================================================================
DELIMITER $$

CREATE TRIGGER trg_student_signup AFTER INSERT ON students FOR EACH ROW
BEGIN
  INSERT INTO activity_log (event, student_id, detail)
  VALUES ('SIGNUP', NEW.id, CONCAT('new student ', NEW.phone));
END$$

CREATE TRIGGER trg_student_login AFTER UPDATE ON students FOR EACH ROW
BEGIN
  IF NOT (OLD.last_login_at <=> NEW.last_login_at) THEN
    INSERT INTO activity_log (event, student_id, detail)
    VALUES ('LOGIN', NEW.id, CONCAT(NEW.phone, ' logged in'));
  END IF;
END$$

-- Business rule enforced inside the database: no booking while the mess is paused.
CREATE TRIGGER trg_booking_paused_ins BEFORE INSERT ON bookings FOR EACH ROW
BEGIN
  IF NEW.status = 'booked' AND EXISTS (
       SELECT 1 FROM pauses p
       WHERE p.student_id = NEW.student_id
         AND NEW.meal_date BETWEEN p.from_date AND p.to_date
         AND (p.ended_on IS NULL OR NEW.meal_date < p.ended_on)) THEN
    SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'Your mess is paused for this date';
  END IF;
END$$

CREATE TRIGGER trg_booking_paused_upd BEFORE UPDATE ON bookings FOR EACH ROW
BEGIN
  IF NEW.status = 'booked' AND EXISTS (
       SELECT 1 FROM pauses p
       WHERE p.student_id = NEW.student_id
         AND NEW.meal_date BETWEEN p.from_date AND p.to_date
         AND (p.ended_on IS NULL OR NEW.meal_date < p.ended_on)) THEN
    SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'Your mess is paused for this date';
  END IF;
END$$

CREATE TRIGGER trg_booking_log_ins AFTER INSERT ON bookings FOR EACH ROW
BEGIN
  INSERT INTO activity_log (event, student_id, detail)
  SELECT UPPER(IF(NEW.status = 'booked', 'book', NEW.status)), NEW.student_id,
         CONCAT(s.phone, ' · ', ms.name, ' · ', NEW.meal_date, ' · ', COALESCE(m.name, NEW.status))
  FROM students s
  JOIN meal_slots ms ON ms.id = NEW.slot_id
  LEFT JOIN messes m ON m.id = NEW.mess_id
  WHERE s.id = NEW.student_id;
END$$

CREATE TRIGGER trg_booking_log_upd AFTER UPDATE ON bookings FOR EACH ROW
BEGIN
  IF NOT (OLD.mess_id <=> NEW.mess_id) OR OLD.status <> NEW.status THEN
    INSERT INTO activity_log (event, student_id, detail)
    SELECT IF(NEW.status = 'paused', 'PAUSED', 'CHANGE'), NEW.student_id,
           CONCAT(s.phone, ' · ', ms.name, ' · ', NEW.meal_date, ' · ',
                  COALESCE(o.name, OLD.status), ' → ', COALESCE(n.name, NEW.status))
    FROM students s
    JOIN meal_slots ms ON ms.id = NEW.slot_id
    LEFT JOIN messes o ON o.id = OLD.mess_id
    LEFT JOIN messes n ON n.id = NEW.mess_id
    WHERE s.id = NEW.student_id;
  END IF;
END$$

CREATE TRIGGER trg_pause_log AFTER INSERT ON pauses FOR EACH ROW
BEGIN
  INSERT INTO activity_log (event, student_id, detail)
  SELECT 'PAUSE', NEW.student_id, CONCAT(s.phone, ' away ', NEW.from_date, ' to ', NEW.to_date)
  FROM students s WHERE s.id = NEW.student_id;
END$$

CREATE TRIGGER trg_resume_log AFTER UPDATE ON pauses FOR EACH ROW
BEGIN
  IF OLD.ended_on IS NULL AND NEW.ended_on IS NOT NULL THEN
    INSERT INTO activity_log (event, student_id, detail)
    SELECT 'RESUME', NEW.student_id, CONCAT(s.phone, ' back from ', NEW.ended_on)
    FROM students s WHERE s.id = NEW.student_id;
  END IF;
END$$

CREATE TRIGGER trg_attendance_log AFTER INSERT ON attendance FOR EACH ROW
BEGIN
  INSERT INTO activity_log (event, student_id, detail)
  SELECT 'SERVED', NEW.student_id,
         CONCAT(s.phone, ' · ', ms.name, ' · ', m.name,
                IF(EXISTS (SELECT 1 FROM bookings b
                           WHERE b.student_id = NEW.student_id AND b.meal_date = NEW.meal_date
                             AND b.slot_id = NEW.slot_id AND b.mess_id = NEW.mess_id
                             AND b.status = 'booked'), '', ' · walk-in'))
  FROM students s
  JOIN meal_slots ms ON ms.id = NEW.slot_id
  JOIN messes m ON m.id = NEW.mess_id
  WHERE s.id = NEW.student_id;
END$$

CREATE TRIGGER trg_donation_log AFTER INSERT ON donations FOR EACH ROW
BEGIN
  INSERT INTO activity_log (event, detail)
  SELECT 'DONATE', CONCAT(NEW.portions, ' portions · ', m.name, ' ', ms.name, ' ', NEW.meal_date, ' → ', n.name)
  FROM messes m, meal_slots ms, ngos n
  WHERE m.id = NEW.mess_id AND ms.id = NEW.slot_id AND n.id = NEW.ngo_id;
END$$

-- =====================================================================
-- STORED PROCEDURES (each one is a single transaction)
-- =====================================================================

-- Going home: record the pause and release every future meal in the range.
CREATE PROCEDURE sp_pause_mess(IN p_student INT UNSIGNED, IN p_from DATE, IN p_to DATE)
BEGIN
  DECLARE EXIT HANDLER FOR SQLEXCEPTION BEGIN ROLLBACK; RESIGNAL; END;
  START TRANSACTION;
    INSERT INTO pauses (student_id, from_date, to_date) VALUES (p_student, p_from, p_to);
    -- Meals already chosen in that range become 'paused' (not counted).
    UPDATE bookings SET status = 'paused', mess_id = NULL
    WHERE student_id = p_student AND meal_date BETWEEN p_from AND p_to;
  COMMIT;
END$$

-- Back early: end every pause that is still running or still in the future.
CREATE PROCEDURE sp_resume_mess(IN p_student INT UNSIGNED, IN p_today DATE)
BEGIN
  DECLARE EXIT HANDLER FOR SQLEXCEPTION BEGIN ROLLBACK; RESIGNAL; END;
  START TRANSACTION;
    UPDATE pauses SET ended_on = p_today
    WHERE student_id = p_student AND ended_on IS NULL AND to_date >= p_today;
    -- Released meals from today on go back to 'skipped' so the student can re-book.
    UPDATE bookings SET status = 'skipped'
    WHERE student_id = p_student AND status = 'paused' AND meal_date >= p_today;
  COMMIT;
END$$

-- After a meal: give the leftover to the NGO that has received the least so far.
-- Leftover to donate = unused buffer + 50% of the no-shows' portions (see v_meal_summary).
CREATE PROCEDURE sp_close_meal(IN p_date DATE, IN p_slot TINYINT UNSIGNED)
BEGIN
  DECLARE done INT DEFAULT 0;
  DECLARE v_mess TINYINT UNSIGNED;
  DECLARE v_portions INT;
  DECLARE v_ngo SMALLINT UNSIGNED;
  DECLARE cur CURSOR FOR
    SELECT mess_id, donate FROM v_meal_summary
    WHERE meal_date = p_date AND slot_id = p_slot AND donate > 0;
  DECLARE CONTINUE HANDLER FOR NOT FOUND SET done = 1;
  DECLARE EXIT HANDLER FOR SQLEXCEPTION BEGIN ROLLBACK; RESIGNAL; END;

  START TRANSACTION;
    DELETE FROM donations WHERE meal_date = p_date AND slot_id = p_slot;
    OPEN cur;
    read_loop: LOOP
      FETCH cur INTO v_mess, v_portions;
      IF done THEN LEAVE read_loop; END IF;
      SELECT n.id INTO v_ngo
      FROM ngos n LEFT JOIN donations d ON d.ngo_id = n.id
      GROUP BY n.id ORDER BY COALESCE(SUM(d.portions), 0), n.id LIMIT 1;
      INSERT INTO donations (meal_date, slot_id, mess_id, ngo_id, portions)
      VALUES (p_date, p_slot, v_mess, v_ngo, v_portions);
    END LOOP;
    CLOSE cur;
  COMMIT;
END$$

DELIMITER ;

-- =====================================================================
-- VIEWS
-- =====================================================================

-- Every student's choice, readable, newest first.
CREATE VIEW v_live_bookings AS
SELECT b.updated_at AS at, s.phone, b.meal_date, ms.name AS meal,
       COALESCE(m.name, '—') AS mess, b.status
FROM bookings b
JOIN students s    ON s.id = b.student_id
JOIN meal_slots ms ON ms.id = b.slot_id
LEFT JOIN messes m ON m.id = b.mess_id
ORDER BY b.updated_at DESC;

-- How much each mess cooks: booked heads + 30% buffer. Skipped and paused are not counted.
CREATE VIEW v_daily_forecast AS
SELECT b.meal_date, m.id AS mess_id, m.name AS mess, ms.id AS slot_id, ms.name AS meal,
       COUNT(*)                                     AS booked,
       CAST(CEIL(COUNT(*) * 1.30) AS SIGNED)        AS cook_for
FROM bookings b
JOIN messes m      ON m.id = b.mess_id
JOIN meal_slots ms ON ms.id = b.slot_id
WHERE b.status = 'booked'
GROUP BY b.meal_date, m.id, m.name, ms.id, ms.name;

-- After the meal: what was cooked, who came, and what goes to NGOs.
--   no_shows  = booked here but not served
--   walk_ins  = served here without a booking here (eaten from the buffer)
--   buffer_left = buffer not eaten by walk-ins
--   donate    = buffer_left + 50% of no-show portions (never more than what is left)
CREATE VIEW v_meal_summary AS
SELECT k.meal_date, k.mess_id, m.name AS mess, k.slot_id, ms.name AS meal,
       CAST(COALESCE(f.booked, 0) AS SIGNED)                         AS booked,
       CAST(COALESCE(f.cook_for, 0) AS SIGNED)                       AS cooked,
       CAST(COALESCE(a.served, 0) AS SIGNED)                         AS served,
       CAST(COALESCE(f.booked, 0) - COALESCE(a.served_booked, 0) AS SIGNED) AS no_shows,
       CAST(COALESCE(a.served, 0) - COALESCE(a.served_booked, 0) AS SIGNED) AS walk_ins,
       CAST(GREATEST(COALESCE(f.cook_for, 0) - COALESCE(f.booked, 0)
                - (COALESCE(a.served, 0) - COALESCE(a.served_booked, 0)), 0) AS SIGNED) AS buffer_left,
       CAST(LEAST(
         GREATEST(COALESCE(f.cook_for, 0) - COALESCE(a.served, 0), 0),
         GREATEST(COALESCE(f.cook_for, 0) - COALESCE(f.booked, 0)
                  - (COALESCE(a.served, 0) - COALESCE(a.served_booked, 0)), 0)
         + FLOOR((COALESCE(f.booked, 0) - COALESCE(a.served_booked, 0)) * 0.5)
       ) AS SIGNED)                                                  AS donate
FROM (
  SELECT meal_date, mess_id, slot_id FROM bookings WHERE status = 'booked'
  UNION
  SELECT meal_date, mess_id, slot_id FROM attendance
) k
JOIN messes m      ON m.id = k.mess_id
JOIN meal_slots ms ON ms.id = k.slot_id
LEFT JOIN v_daily_forecast f
       ON f.meal_date = k.meal_date AND f.mess_id = k.mess_id AND f.slot_id = k.slot_id
LEFT JOIN (
  SELECT att.meal_date, att.mess_id, att.slot_id,
         COUNT(*) AS served,
         SUM(EXISTS (SELECT 1 FROM bookings b
                     WHERE b.student_id = att.student_id AND b.meal_date = att.meal_date
                       AND b.slot_id = att.slot_id AND b.mess_id = att.mess_id
                       AND b.status = 'booked')) AS served_booked
  FROM attendance att
  GROUP BY att.meal_date, att.mess_id, att.slot_id
) a ON a.meal_date = k.meal_date AND a.mess_id = k.mess_id AND a.slot_id = k.slot_id;

-- Total food each NGO has received.
CREATE VIEW v_ngo_totals AS
SELECT n.id, n.name, n.area, COUNT(d.id) AS deliveries, CAST(COALESCE(SUM(d.portions), 0) AS SIGNED) AS portions
FROM ngos n LEFT JOIN donations d ON d.ngo_id = n.id
GROUP BY n.id, n.name, n.area;
