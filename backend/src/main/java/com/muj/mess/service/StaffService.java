package com.muj.mess.service;

import com.muj.mess.config.AppConfig;
import com.muj.mess.db.Database;
import com.muj.mess.model.Booking;
import com.muj.mess.model.Requests;
import com.muj.mess.model.Student;
import com.muj.mess.repository.BookingRepository;
import com.muj.mess.repository.MealRepository;
import com.muj.mess.repository.MenuRepository;
import com.muj.mess.repository.StudentRepository;
import com.muj.mess.web.ApiException;

import java.sql.SQLException;
import java.sql.SQLIntegrityConstraintViolationException;
import java.time.LocalDate;
import java.util.List;
import java.util.Map;
import java.util.Optional;

/** What mess-counter staff can do: mark a student served, close a meal so leftovers go to an NGO. */
public class StaffService {

    private final Database db;
    private final StudentRepository students;
    private final MenuRepository menu;
    private final BookingRepository bookings;
    private final MealRepository meals;

    public StaffService(Database db, StudentRepository students, MenuRepository menu,
                        BookingRepository bookings, MealRepository meals) {
        this.db = db;
        this.students = students;
        this.menu = menu;
        this.bookings = bookings;
        this.meals = meals;
    }

    /** Record that a student ate. Works for walk-ins too; they come out of the 30% buffer. */
    public Map<String, Object> serve(Requests.Serve req) throws SQLException {
        LocalDate today = AppConfig.today();
        return db.inTransaction(conn -> {
            Student student = students.findByPhone(conn, req.phone())
                    .orElseThrow(() -> new ApiException.NotFound("No student on the roster with this number"));
            if (!menu.slotExists(conn, req.slotId()) || !menu.messExists(conn, req.messId())) {
                throw new ApiException.BadRequest("Unknown meal or mess");
            }
            Optional<Booking> booking = bookings.at(conn, student.id(), today, req.slotId());
            try {
                meals.serve(conn, student.id(), today, req.slotId(), req.messId());
            } catch (SQLIntegrityConstraintViolationException e) { // UNIQUE(student, date, slot) in attendance
                throw new ApiException.Conflict("Already served this meal today");
            }
            return Map.of(
                    "served", true,
                    "name", student.fullName(),
                    "booked_here", booking.map(b -> b.isBookedAt(req.messId())).orElse(false),
                    "booking", booking.map(Booking::label).orElse("none"));
        });
    }

    /** Runs sp_close_meal, then returns the donations it made for that meal. */
    public List<Map<String, Object>> closeMeal(Requests.CloseMeal req) throws SQLException {
        return db.inTransaction(conn -> {
            meals.closeMeal(conn, req.mealDate(), req.slotId());
            return meals.donationsOn(conn, req.mealDate()).stream()
                    .filter(d -> req.slotId().equals(((Number) d.get("slot_id")).intValue()))
                    .toList();
        });
    }
}
