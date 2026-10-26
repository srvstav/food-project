package com.muj.mess.repository;

import java.sql.Connection;
import java.sql.SQLException;
import java.time.LocalDate;
import java.util.List;
import java.util.Map;

/** SQL for the public dashboard: activity feed, forecasts, hostel split. OOP: Inheritance from BaseRepository. */
public class DashboardRepository extends BaseRepository {

    public List<Map<String, Object>> recentActivity(Connection conn, int limit) throws SQLException {
        return queryAll(conn, "SELECT id, DATE_FORMAT(at, '%H:%i:%s') AS at, event, detail "
                + "FROM activity_log ORDER BY id DESC LIMIT ?", limit);
    }

    /** How many booked each meal, and how many to cook for (booked + 30%). */
    public List<Map<String, Object>> forecast(Connection conn, LocalDate date) throws SQLException {
        return queryAll(conn, "SELECT mess, meal, booked, cook_for FROM v_daily_forecast "
                + "WHERE meal_date = ? ORDER BY slot_id, mess_id", date);
    }

    public List<Map<String, Object>> hostelSplit(Connection conn, LocalDate date) throws SQLException {
        return queryAll(conn, "SELECT hostel, mess, SUM(booked) AS booked FROM v_hostel_split WHERE meal_date = ? "
                + "GROUP BY hostel_id, hostel, mess ORDER BY hostel_id, mess", date);
    }
}
