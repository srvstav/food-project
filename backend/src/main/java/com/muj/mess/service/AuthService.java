package com.muj.mess.service;

import com.muj.mess.db.Database;
import com.muj.mess.model.Student;
import com.muj.mess.repository.StudentRepository;
import com.muj.mess.web.ApiException;

import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.security.SecureRandom;
import java.sql.SQLException;
import java.util.HashMap;
import java.util.Map;

/**
 * Login with a one-time code, and the staff PIN.
 *
 * Demo login: the server makes a 6-digit code and the page shows it (no SMS account needed).
 * Codes are kept hashed in memory, last 5 minutes, work once, and allow 5 wrong tries.
 *
 * OOP: Composition + Dependency Injection — AuthService doesn't create its helpers; Main passes them
 *      in through the constructor. That makes each part replaceable and easy to test.
 */
public class AuthService {

    private static final long CODE_TTL_MILLIS = 5 * 60 * 1000;
    private static final int CODE_TRIES = 5;

    /** OOP: private nested record — a type only AuthService needs. */
    private record PendingCode(String hash, long expiresAt, int triesLeft) {
        PendingCode withOneLessTry() { // records are immutable, so "changing" one means making a new one
            return new PendingCode(hash, expiresAt, triesLeft - 1);
        }
    }

    private final Database db;
    private final StudentRepository students;
    private final TokenService tokens;
    private final RateLimiter checks = new RateLimiter(10, 10 * 60 * 1000); // 10 tries per IP per 10 minutes
    private final String staffPin;
    private final Map<String, PendingCode> codes = new HashMap<>(); // phone -> code waiting to be typed
    private final SecureRandom random = new SecureRandom();

    public AuthService(Database db, StudentRepository students, TokenService tokens, String staffPin) {
        this.db = db;
        this.students = students;
        this.tokens = tokens;
        this.staffPin = staffPin;
    }

    /** Step 1: rate-limit, then make a code. Returns the code so the page can show it (demo mode). */
    public String sendCode(String phone, String clientIp) {
        if (!checks.tryAcquire(clientIp)) {
            throw new ApiException.TooManyRequests("Too many tries. Wait 10 minutes and try again");
        }
        String code = String.format("%06d", random.nextInt(1_000_000));
        synchronized (codes) {
            codes.put(phone, new PendingCode(hash(phone, code), System.currentTimeMillis() + CODE_TTL_MILLIS, CODE_TRIES));
        }
        return code;
    }

    /** Step 2: check the typed code; on success return the student's id (enrolling new numbers). */
    public int verifyCode(String phone, String code) throws SQLException {
        synchronized (codes) {
            PendingCode pending = codes.get(phone);
            if (pending == null || pending.expiresAt() < System.currentTimeMillis()) {
                codes.remove(phone);
                throw new ApiException.BadRequest("That code expired. Tap “Resend code”");
            }
            if (!same(pending.hash(), hash(phone, code))) {
                if (pending.triesLeft() <= 1) {
                    codes.remove(phone);
                    throw new ApiException.TooManyRequests("Too many wrong codes. Tap “Resend code”");
                }
                codes.put(phone, pending.withOneLessTry());
                throw new ApiException.BadRequest("Wrong code. Check it and try again");
            }
            codes.remove(phone); // one use only
        }
        return db.inTransaction(conn -> {
            Student student = students.findByPhone(conn, phone).orElse(null);
            if (student == null) {
                students.enrolGuest(conn, phone);
                student = students.findByPhone(conn, phone).orElseThrow();
            }
            if (!student.isActive()) throw new ApiException.Forbidden("This student has left or graduated");
            students.recordLogin(conn, student.id(), "demo"); // fires the LOGIN trigger
            return student.id();
        });
    }

    public String tokenFor(int studentId) {
        return tokens.make(studentId);
    }

    /** The logged-in student's id from "Authorization: Bearer <token>", or a 401. */
    public int requireStudent(String authorizationHeader) {
        return tokens.studentIdFrom(authorizationHeader);
    }

    /** Staff screens send "X-Staff-Pin: <pin>". */
    public void requireStaff(String pin) {
        if (pin.isEmpty() || !same(pin, staffPin)) throw new ApiException.Forbidden("Wrong staff PIN");
    }

    private String hash(String phone, String code) {
        return tokens.sign(phone + ":" + code);
    }

    private static boolean same(String a, String b) { // constant-time compare
        return MessageDigest.isEqual(a.getBytes(StandardCharsets.UTF_8), b.getBytes(StandardCharsets.UTF_8));
    }
}
