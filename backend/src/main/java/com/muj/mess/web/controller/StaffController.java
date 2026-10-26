package com.muj.mess.web.controller;

import com.muj.mess.model.Requests;
import com.muj.mess.service.AuthService;
import com.muj.mess.service.StaffService;
import com.muj.mess.web.ApiRequest;
import com.muj.mess.web.Controller;
import com.muj.mess.web.Router;

import java.util.Map;

/** Mess-counter endpoints. Every one needs the staff PIN in the X-Staff-Pin header. */
public class StaffController implements Controller {

    private final AuthService auth;
    private final StaffService staff;

    public StaffController(AuthService auth, StaffService staff) {
        this.auth = auth;
        this.staff = staff;
    }

    @Override
    public void register(Router r) {
        r.get("/staff/check", req -> {
            checkPin(req);
            return Map.of("status", "ok");
        });

        r.post("/staff/serve", req -> {
            checkPin(req);
            return staff.serve(req.body(Requests.Serve.class));
        });

        r.post("/staff/close-meal", req -> {
            checkPin(req);
            return Map.of("donations", staff.closeMeal(req.body(Requests.CloseMeal.class)));
        });
    }

    private void checkPin(ApiRequest req) {
        auth.requireStaff(req.header("X-Staff-Pin"));
    }
}
