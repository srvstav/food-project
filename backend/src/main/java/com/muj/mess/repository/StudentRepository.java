package com.muj.mess.repository;

import com.muj.mess.model.Student;

import java.security.SecureRandom;
import java.sql.Connection;
import java.sql.SQLException;
import java.sql.SQLIntegrityConstraintViolationException;
import java.util.Map;
import java.util.Optional;

/**
 * SQL for the students roster and logins.
 * OOP: Inheritance — "extends BaseRepository", so it gets queryOne/queryAll/execute for free.
 * Repository Pattern: all SQL about students lives here and nowhere else.
 */
public class StudentRepository extends BaseRepository {

    private final SecureRandom random = new SecureRandom();

    public Optional<Student> findByPhone(Connection conn, String phone) throws SQLException {
        return queryOne(conn, "SELECT id, full_name, status FROM students WHERE phone = ?",
                rs -> new Student(rs.getInt("id"), rs.getString("full_name"), rs.getString("status")), // lambda = RowMapper
                phone);
    }

    /**
     * A number that isn't on the roster joins it on first login (fires the ENROL trigger).
     * Placeholder details, so a demo never stops at the door; the mess office can correct them later.
     */
    public void enrolGuest(Connection conn, String phone) throws SQLException {
        String[] regNos = {"9" + phone.substring(2), "98" + String.format("%07d", random.nextInt(10_000_000))};
        for (String regNo : regNos) { // second try only if the first reg_no is taken
            try {
                execute(conn, "INSERT INTO students (reg_no, full_name, gender, phone, email, programme_id, "
                                + "year_of_study, hostel_id, room_no, joined_on) "
                                + "VALUES (?, ?, 'M', ?, ?, 1, 1, 1, '100', CURRENT_DATE)",
                        regNo, "Guest " + phone.substring(6), phone, "guest." + phone + "@muj.manipal.edu");
                return;
            } catch (SQLIntegrityConstraintViolationException taken) {
                // reg_no already used: try the next one
            }
        }
    }

    public void recordLogin(Connection conn, int studentId, String method) throws SQLException {
        execute(conn, "INSERT INTO logins (student_id, firebase_uid) VALUES (?, ?)", studentId, method); // LOGIN trigger
    }

    public Optional<Map<String, Object>> profile(Connection conn, int studentId) throws SQLException {
        return queryOne(conn, "SELECT reg_no, full_name, phone, programme, year_of_study, hostel, room_no, "
                + "meals_booked, meals_eaten FROM v_student_directory WHERE id = ?", BaseRepository::toMap, studentId);
    }

    public Map<String, Object> rosterCounts(Connection conn) throws SQLException {
        return queryOne(conn, "SELECT COUNT(*) AS students, COUNT(DISTINCT hostel_id) AS hostels, "
                        + "(SELECT COUNT(DISTINCT student_id) FROM logins) AS logged_in "
                        + "FROM students WHERE status = 'active'", BaseRepository::toMap)
                .orElseThrow();
    }
}
