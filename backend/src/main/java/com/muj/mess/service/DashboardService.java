package com.muj.mess.service;

import com.muj.mess.config.AppConfig;
import com.muj.mess.db.Database;
import com.muj.mess.repository.DashboardRepository;
import com.muj.mess.repository.MealRepository;
import com.muj.mess.repository.StudentRepository;

import java.sql.SQLException;
import java.time.LocalDate;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.regex.Pattern;

/** The public live board: no personal data, so phone numbers in the feed are masked. */
public class DashboardService {

    private static final Pattern PHONE = Pattern.compile("\\b([6-9]\\d)\\d{5}(\\d{3})\\b");

    private final Database db;
    private final DashboardRepository dashboard;
    private final MealRepository meals;
    private final StudentRepository students;

    public DashboardService(Database db, DashboardRepository dashboard, MealRepository meals, StudentRepository students) {
        this.db = db;
        this.dashboard = dashboard;
        this.meals = meals;
        this.students = students;
    }

    public List<Map<String, Object>> forecast(LocalDate day) throws SQLException {
        return db.inTransaction(conn -> dashboard.forecast(conn, day));
    }

    public Map<String, Object> live(int limit) throws SQLException {
        LocalDate today = AppConfig.today();
        return db.inTransaction(conn -> {
            List<Map<String, Object>> activity = dashboard.recentActivity(conn, limit);
            for (Map<String, Object> a : activity) { // 9876543210 -> 98xxxxx210
                if (a.get("detail") instanceof String detail) a.put("detail", PHONE.matcher(detail).replaceAll("$1xxxxx$2"));
            }
            Map<String, Object> out = new LinkedHashMap<>();
            out.put("meal_date", today);
            out.put("activity", activity);
            out.put("summary", meals.summary(conn, today));
            out.put("roster", students.rosterCounts(conn));
            out.put("earnings", meals.earnings(conn, today, AppConfig.now().toLocalTime(), 7));
            out.put("tomorrow", dashboard.forecast(conn, today.plusDays(1)));
            out.put("hostels", dashboard.hostelSplit(conn, today));
            out.put("donations", meals.donationsOn(conn, today));
            out.put("ngos", meals.ngoTotals(conn));
            return out;
        });
    }
}
