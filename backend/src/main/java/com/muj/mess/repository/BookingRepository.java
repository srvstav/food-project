package com.muj.mess.repository;

import com.muj.mess.model.Booking;
import com.muj.mess.model.MealStatus;

import java.sql.Connection;
import java.sql.SQLException;
import java.time.LocalDate;
import java.util.List;
import java.util.Map;
import java.util.Optional;

/** SQL for bookings and pauses (going home). OOP: Inheritance from BaseRepository. */
public class BookingRepository extends BaseRepository {

    /** Book or skip one meal; booking the same meal again changes it. The PAUSE trigger blocks paused days. */
    public void upsert(Connection conn, int studentId, LocalDate date, int slotId, Integer messId, MealStatus status)
            throws SQLException {
        execute(conn, "INSERT INTO bookings (student_id, meal_date, slot_id, mess_id, status) VALUES (?, ?, ?, ?, ?) "
                        + "AS new ON DUPLICATE KEY UPDATE mess_id = new.mess_id, status = new.status",
                studentId, date, slotId, messId, status.dbValue());
    }

    public List<Map<String, Object>> forDay(Connection conn, int studentId, LocalDate date) throws SQLException {
        return queryAll(conn, "SELECT slot_id, mess_id, status FROM bookings WHERE student_id = ? AND meal_date = ?",
                studentId, date);
    }

    public Optional<Booking> at(Connection conn, int studentId, LocalDate date, int slotId) throws SQLException {
        return queryOne(conn, "SELECT b.mess_id, m.name AS mess, b.status FROM bookings b "
                        + "LEFT JOIN messes m ON m.id = b.mess_id "
                        + "WHERE b.student_id = ? AND b.meal_date = ? AND b.slot_id = ?",
                rs -> new Booking(rs.getObject("mess_id", Integer.class), rs.getString("mess"),
                        MealStatus.fromDb(rs.getString("status"))),
                studentId, date, slotId);
    }

    // ---------- pause / resume (stored procedures) ----------

    public void pause(Connection conn, int studentId, LocalDate from, LocalDate to) throws SQLException {
        execute(conn, "CALL sp_pause_mess(?, ?, ?)", studentId, from, to);
    }

    public void resume(Connection conn, int studentId, LocalDate today) throws SQLException {
        execute(conn, "CALL sp_resume_mess(?, ?)", studentId, today);
    }

    /** Pauses still running or still to come. */
    public List<Map<String, Object>> activePauses(Connection conn, int studentId, LocalDate today) throws SQLException {
        return queryAll(conn, "SELECT id, from_date, to_date FROM pauses "
                + "WHERE student_id = ? AND ended_on IS NULL AND to_date >= ? ORDER BY from_date", studentId, today);
    }

    public boolean isPaused(Connection conn, int studentId, LocalDate day) throws SQLException {
        return exists(conn, "SELECT 1 FROM pauses WHERE student_id = ? AND ? BETWEEN from_date AND to_date "
                + "AND (ended_on IS NULL OR ? < ended_on) LIMIT 1", studentId, day, day);
    }
}
