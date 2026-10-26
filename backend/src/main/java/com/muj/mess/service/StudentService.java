package com.muj.mess.service;

import com.muj.mess.config.AppConfig;
import com.muj.mess.db.Database;
import com.muj.mess.model.Requests;
import com.muj.mess.repository.BookingRepository;
import com.muj.mess.repository.MenuRepository;
import com.muj.mess.repository.StudentRepository;
import com.muj.mess.web.ApiException;

import java.sql.SQLException;
import java.time.LocalDate;
import java.time.temporal.ChronoUnit;
import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

/**
 * What a student can do: see the menu, book or skip meals, pause when going home.
 * Business rules (date limits, pause length) live here; the SQL lives in the repositories.
 * OOP: Layered design — controller → service → repository. Each layer only talks to the one below.
 */
public class StudentService {

    private final Database db;
    private final StudentRepository students;
    private final MenuRepository menu;
    private final BookingRepository bookings;

    public StudentService(Database db, StudentRepository students, MenuRepository menu, BookingRepository bookings) {
        this.db = db;
        this.students = students;
        this.menu = menu;
        this.bookings = bookings;
    }

    public Map<String, Object> profile(int studentId) throws SQLException {
        return db.inTransaction(conn -> students.profile(conn, studentId))
                .orElseThrow(ApiException.Unauthorized::new); // OOP: constructor reference
    }

    /** The menu as slots → messes → dishes (the shape the website draws). */
    public List<Map<String, Object>> menu() throws SQLException {
        List<Map<String, Object>> rows = db.inTransaction(menu::menu); // OOP: method reference as a SqlWork
        Map<Object, Map<String, Object>> slots = new LinkedHashMap<>();
        for (Map<String, Object> r : rows) {
            Map<String, Object> slot = slots.computeIfAbsent(r.get("slot_id"), id -> {
                Map<String, Object> s = new LinkedHashMap<>();
                s.put("slot_id", id);
                s.put("code", r.get("slot_code"));
                s.put("name", r.get("slot"));
                s.put("starts_at", r.get("starts_at"));
                s.put("ends_at", r.get("ends_at"));
                s.put("messes", new LinkedHashMap<Object, Map<String, Object>>());
                return s;
            });
            @SuppressWarnings("unchecked")
            Map<Object, Map<String, Object>> messes = (Map<Object, Map<String, Object>>) slot.get("messes");
            Map<String, Object> mess = messes.computeIfAbsent(r.get("mess_id"), id -> {
                Map<String, Object> m = new LinkedHashMap<>();
                m.put("mess_id", id);
                m.put("name", r.get("mess"));
                m.put("dishes", new ArrayList<Object>());
                return m;
            });
            @SuppressWarnings("unchecked")
            List<Object> dishes = (List<Object>) mess.get("dishes");
            dishes.add(r.get("dish"));
        }
        List<Map<String, Object>> out = new ArrayList<>();
        for (Map<String, Object> slot : slots.values()) {
            slot.put("messes", new ArrayList<>(((Map<?, ?>) slot.get("messes")).values()));
            out.add(slot);
        }
        return out;
    }

    public Map<String, Object> myDay(int studentId, LocalDate day) throws SQLException {
        return db.inTransaction(conn -> Map.of(
                "meal_date", day,
                "paused", bookings.isPaused(conn, studentId, day),
                "bookings", bookings.forDay(conn, studentId, day)));
    }

    /** Book a mess for one meal, or skip it. Returns "booked" or "skipped". */
    public String book(int studentId, Requests.BookMeal req) throws SQLException {
        LocalDate today = AppConfig.today();
        if (req.mealDate().isBefore(today) || req.mealDate().isAfter(today.plusDays(AppConfig.BOOKING_DAYS_AHEAD))) {
            throw new ApiException.BadRequest("Pick a date from today to " + AppConfig.BOOKING_DAYS_AHEAD + " days ahead");
        }
        return db.inTransaction(conn -> {
            if (!menu.slotExists(conn, req.slotId()) || (req.messId() != null && !menu.messExists(conn, req.messId()))) {
                throw new ApiException.BadRequest("Unknown meal or mess");
            }
            // The PAUSE trigger in MySQL refuses this if the student is away that day (→ 409 for the browser).
            bookings.upsert(conn, studentId, req.mealDate(), req.slotId(), req.messId(), req.status());
            return req.status().dbValue();
        });
    }

    public List<Map<String, Object>> myPauses(int studentId) throws SQLException {
        return db.inTransaction(conn -> bookings.activePauses(conn, studentId, AppConfig.today()));
    }

    public void pause(int studentId, Requests.Pause req) throws SQLException {
        if (req.fromDate().isBefore(AppConfig.today())) {
            throw new ApiException.BadRequest("You can't pause a day that has already passed");
        }
        if (ChronoUnit.DAYS.between(req.fromDate(), req.toDate()) >= AppConfig.MAX_PAUSE_DAYS) {
            throw new ApiException.BadRequest("A pause can be at most " + AppConfig.MAX_PAUSE_DAYS + " days");
        }
        db.inTransaction(conn -> {
            bookings.pause(conn, studentId, req.fromDate(), req.toDate()); // stored procedure sp_pause_mess
            return null;
        });
    }

    public void resume(int studentId) throws SQLException {
        db.inTransaction(conn -> {
            bookings.resume(conn, studentId, AppConfig.today()); // stored procedure sp_resume_mess
            return null;
        });
    }
}
