package com.muj.mess.repository;

import java.sql.Connection;
import java.sql.SQLException;
import java.time.LocalDate;
import java.time.LocalTime;
import java.util.List;
import java.util.Map;

/** SQL for serving meals, closing them, donations and the ledger. OOP: Inheritance from BaseRepository. */
public class MealRepository extends BaseRepository {

    /** Staff marked this student as served. A second serve of the same meal breaks a UNIQUE key. */
    public void serve(Connection conn, int studentId, LocalDate date, int slotId, int messId) throws SQLException {
        execute(conn, "INSERT INTO attendance (student_id, meal_date, slot_id, mess_id) VALUES (?, ?, ?, ?)",
                studentId, date, slotId, messId);
    }

    /** sp_close_meal gives leftover food to the NGO that has received the least so far. */
    public void closeMeal(Connection conn, LocalDate date, int slotId) throws SQLException {
        execute(conn, "CALL sp_close_meal(?, ?)", date, slotId);
    }

    public List<Map<String, Object>> summary(Connection conn, LocalDate date) throws SQLException {
        return queryAll(conn, "SELECT mess_id, mess, slot_id, meal, booked, cooked, served, no_shows, walk_ins, "
                + "buffer_left, donate FROM v_meal_summary WHERE meal_date = ? ORDER BY slot_id, mess_id", date);
    }

    public List<Map<String, Object>> donationsOn(Connection conn, LocalDate date) throws SQLException {
        return queryAll(conn, "SELECT d.slot_id, ms.name AS meal, m.name AS mess, n.name AS ngo, n.area, d.portions "
                + "FROM donations d JOIN messes m ON m.id = d.mess_id JOIN meal_slots ms ON ms.id = d.slot_id "
                + "JOIN ngos n ON n.id = d.ngo_id WHERE d.meal_date = ? ORDER BY d.slot_id, d.mess_id", date);
    }

    /**
     * Profit per mess per meal for the last `days` days. Today counts only meals that have started,
     * so a dinner that hasn't been served yet doesn't show up as a loss.
     */
    public List<Map<String, Object>> earnings(Connection conn, LocalDate today, LocalTime now, int days)
            throws SQLException {
        return queryAll(conn, "SELECT meal_date, mess_id, mess, slot_id, meal, booked, cooked, served, no_shows, "
                        + "donated, wasted, revenue, food_cost, profit FROM v_mess_earnings "
                        + "WHERE meal_date BETWEEN ? AND ? AND (meal_date < ? OR starts_at <= ?) "
                        + "ORDER BY meal_date, slot_id, mess_id",
                today.minusDays(days - 1L), today, today, now.withNano(0).toString());
    }

    public List<Map<String, Object>> ngoTotals(Connection conn) throws SQLException {
        return queryAll(conn, "SELECT name, area, deliveries, portions FROM v_ngo_totals ORDER BY portions DESC, name");
    }
}
