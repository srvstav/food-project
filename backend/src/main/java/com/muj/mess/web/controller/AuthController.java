package com.muj.mess.web.controller;

import com.muj.mess.model.Requests;
import com.muj.mess.service.AuthService;
import com.muj.mess.service.StudentService;
import com.muj.mess.web.ApiException;
import com.muj.mess.web.Controller;
import com.muj.mess.web.Router;

import java.util.Map;

/**
 * Login endpoints. Controllers are thin: read the request, call a service, return the answer.
 * OOP: Interface implementation — "implements Controller", so it must provide register().
 */
public class AuthController implements Controller {

    private final AuthService auth;
    private final StudentService students;

    public AuthController(AuthService auth, StudentService students) {
        this.auth = auth;
        this.students = students;
    }

    @Override
    public void register(Router r) {
        // Step 1: the page asks for a code. No SMS account here, so the code comes back to show on screen.
        r.post("/auth/check", req -> {
            Requests.Phone body = req.body(Requests.Phone.class);
            return Map.of("on_roster", true, "demo_code", auth.sendCode(body.phone(), req.clientIp()));
        });

        // Step 2: the student types the code; we answer with a session token.
        r.post("/auth/demo-verify", req -> {
            Requests.DemoVerify body = req.body(Requests.DemoVerify.class);
            int studentId = auth.verifyCode(body.phone(), body.otp());
            return Map.of("token", auth.tokenFor(studentId), "student", students.profile(studentId));
        });

        // Real SMS (Firebase) login isn't part of the Java version: the site uses the code login above.
        r.post("/auth/login", req -> {
            throw new ApiException.Unavailable("SMS login is off; use the on-screen code");
        });

        r.get("/me", req -> Map.of("student", students.profile(auth.requireStudent(req.header("Authorization")))));
    }
}
