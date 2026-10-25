-- MUJ Mess — one fee, eat at either mess, book each meal.
-- Run via db/setup.sh (also creates the app user and .env).
DROP DATABASE IF EXISTS mess;
CREATE DATABASE mess CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci;
USE mess;

CREATE TABLE messes (
  id   TINYINT UNSIGNED PRIMARY KEY,
  name VARCHAR(40) NOT NULL UNIQUE
);

CREATE TABLE meal_slots (
  id         TINYINT UNSIGNED PRIMARY KEY,
  code       VARCHAR(16) NOT NULL UNIQUE,
  name       VARCHAR(32) NOT NULL,
  starts_at  TIME NOT NULL,
  ends_at    TIME NOT NULL
);

-- Same weekly menu for the demo; one row per dish.
CREATE TABLE menu_items (
  id       INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
  mess_id  TINYINT UNSIGNED NOT NULL,
  slot_id  TINYINT UNSIGNED NOT NULL,
  dish     VARCHAR(80) NOT NULL,
  FOREIGN KEY (mess_id) REFERENCES messes(id),
  FOREIGN KEY (slot_id) REFERENCES meal_slots(id)
);

CREATE TABLE students (
  id             INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
  phone          CHAR(10) NOT NULL UNIQUE,
  created_at     DATETIME(3) NOT NULL DEFAULT CURRENT_TIMESTAMP(3),
  last_login_at  DATETIME(3) NULL,
  CONSTRAINT chk_phone CHECK (phone REGEXP '^[6-9][0-9]{9}$')
);

-- Only a keyed hash (HMAC-SHA256) of the code is stored, never the code itself.
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

-- One row per student per day per meal. mess_id NULL + status 'skipped' = not eating, not counted.
CREATE TABLE bookings (
  id          INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
  student_id  INT UNSIGNED NOT NULL,
  meal_date   DATE NOT NULL,
  slot_id     TINYINT UNSIGNED NOT NULL,
  mess_id     TINYINT UNSIGNED NULL,
  status      ENUM('booked','skipped') NOT NULL,
  created_at  DATETIME(3) NOT NULL DEFAULT CURRENT_TIMESTAMP(3),
  updated_at  DATETIME(3) NOT NULL DEFAULT CURRENT_TIMESTAMP(3) ON UPDATE CURRENT_TIMESTAMP(3),
  UNIQUE KEY uq_one_choice (student_id, meal_date, slot_id),
  INDEX idx_forecast (meal_date, slot_id, mess_id, status),
  FOREIGN KEY (student_id) REFERENCES students(id),
  FOREIGN KEY (slot_id)    REFERENCES meal_slots(id),
  FOREIGN KEY (mess_id)    REFERENCES messes(id),
  CONSTRAINT chk_status_mess CHECK (
    (status = 'booked' AND mess_id IS NOT NULL) OR (status = 'skipped' AND mess_id IS NULL)
  )
);

-- Filled only by triggers — the "live feed" to watch in Workbench.
CREATE TABLE activity_log (
  id          BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
  at          DATETIME(3) NOT NULL DEFAULT CURRENT_TIMESTAMP(3),
  event       VARCHAR(20) NOT NULL,
  student_id  INT UNSIGNED NULL,
  detail      VARCHAR(200) NOT NULL
);

DELIMITER $$

CREATE TRIGGER trg_student_new AFTER INSERT ON students FOR EACH ROW
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

CREATE TRIGGER trg_booking_new AFTER INSERT ON bookings FOR EACH ROW
BEGIN
  INSERT INTO activity_log (event, student_id, detail)
  SELECT IF(NEW.status = 'booked', 'BOOK', 'SKIP'), NEW.student_id,
         CONCAT(s.phone, ' · ', ms.name, ' · ', NEW.meal_date, ' · ', COALESCE(m.name, 'skipped'))
  FROM students s
  JOIN meal_slots ms ON ms.id = NEW.slot_id
  LEFT JOIN messes m ON m.id = NEW.mess_id
  WHERE s.id = NEW.student_id;
END$$

CREATE TRIGGER trg_booking_change AFTER UPDATE ON bookings FOR EACH ROW
BEGIN
  IF NOT (OLD.mess_id <=> NEW.mess_id) OR OLD.status <> NEW.status THEN
    INSERT INTO activity_log (event, student_id, detail)
    SELECT 'CHANGE', NEW.student_id,
           CONCAT(s.phone, ' · ', ms.name, ' · ', NEW.meal_date, ' · ',
                  COALESCE(o.name, 'skipped'), ' → ', COALESCE(n.name, 'skipped'))
    FROM students s
    JOIN meal_slots ms ON ms.id = NEW.slot_id
    LEFT JOIN messes o ON o.id = OLD.mess_id
    LEFT JOIN messes n ON n.id = NEW.mess_id
    WHERE s.id = NEW.student_id;
  END IF;
END$$

DELIMITER ;

-- Readable list of every choice, newest first.
CREATE VIEW v_live_bookings AS
SELECT b.updated_at AS at, s.phone, b.meal_date, ms.name AS meal,
       COALESCE(m.name, '—') AS mess, b.status
FROM bookings b
JOIN students s    ON s.id = b.student_id
JOIN meal_slots ms ON ms.id = b.slot_id
LEFT JOIN messes m ON m.id = b.mess_id
ORDER BY b.updated_at DESC;

-- How much each mess should cook: booked heads + 30% buffer. Skips are not counted.
CREATE VIEW v_daily_forecast AS
SELECT b.meal_date, m.name AS mess, ms.name AS meal, ms.id AS slot_order,
       COUNT(*)                AS booked,
       CEIL(COUNT(*) * 1.30)   AS cook_for
FROM bookings b
JOIN messes m      ON m.id = b.mess_id
JOIN meal_slots ms ON ms.id = b.slot_id
WHERE b.status = 'booked'
GROUP BY b.meal_date, m.id, m.name, ms.id, ms.name;
