package com.muj.mess.web.controller;

import com.muj.mess.config.AppConfig;
import com.muj.mess.model.Requests;
import com.muj.mess.service.AuthService;
import com.muj.mess.service.StudentService;
import com.muj.mess.web.ApiException;
import com.muj.mess.web.ApiRequest;
import com.muj.mess.web.Controller;
import com.muj.mess.web.Router;

import java.time.LocalDate;
import java.time.format.DateTimeParseException;
import java.util.Map;

/** Student endpoints: menu, bookings, pause and resume. */
public class StudentController implements Controller {

    private final AuthService auth;
    private final StudentService students;

    public StudentController(AuthService auth, StudentService students) {
        this.auth = auth;
        this.students = students;
    }

    @Override
    public void register(Router r) {
        r.get("/menu", req -> Map.of("slots", students.menu()));

        r.get("/bookings/me", req -> students.myDay(me(req), dateParam(req)));

        r.post("/bookings", req -> {
            int id = me(req);
            return Map.of("status", students.book(id, req.body(Requests.BookMeal.class)));
        });

        r.get("/pause/me", req -> Map.of("pauses", students.myPauses(me(req))));

        r.post("/pause", req -> {
            int id = me(req);
            students.pause(id, req.body(Requests.Pause.class));
            return Map.of("status", "paused");
        });

        r.post("/resume", req -> {
            students.resume(me(req));
            return Map.of("status", "resumed");
        });
    }

    /** The logged-in student, or a 401. */
    private int me(ApiRequest req) {
        return auth.requireStudent(req.header("Authorization"));
    }

    private static LocalDate dateParam(ApiRequest req) {
        String value = req.query("meal_date");
        if (value == null || value.isBlank()) return AppConfig.today();
        try {
            return LocalDate.parse(value);
        } catch (DateTimeParseException e) {
            throw new ApiException.BadRequest("Dates look like 2026-10-27");
        }
    }
}
