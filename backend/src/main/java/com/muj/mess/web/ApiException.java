package com.muj.mess.web;

/**
 * An error the browser should see, with the right HTTP status code.
 *
 * OOP: Abstract class + Inheritance — each kind of error below "extends ApiException".
 * OOP: Polymorphism — the server catches every one as ApiException and calls status();
 *      each subclass answers with its own number (method overriding). No if/else chain needed.
 * OOP: Custom exception — extends RuntimeException, Java's own exception class.
 */
public abstract class ApiException extends RuntimeException {

    protected ApiException(String message) {
        super(message); // OOP: super(...) — calls the parent class's constructor
    }

    /** The HTTP status code for this kind of error. Every subclass must say which. */
    public abstract int status();

    // OOP: static nested subclasses — small, related classes kept together in one file.

    /** 400: the input is wrong (bad date, unknown meal …). */
    public static class BadRequest extends ApiException {
        public BadRequest(String message) { super(message); }
        @Override public int status() { return 400; }
    }

    /** 401: not logged in, or the session expired. */
    public static class Unauthorized extends ApiException {
        public Unauthorized() { super("Please log in again"); }
        @Override public int status() { return 401; }
    }

    /** 403: logged in, but not allowed (wrong staff PIN, graduated student). */
    public static class Forbidden extends ApiException {
        public Forbidden(String message) { super(message); }
        @Override public int status() { return 403; }
    }

    /** 404: the thing asked for doesn't exist. */
    public static class NotFound extends ApiException {
        public NotFound(String message) { super(message); }
        @Override public int status() { return 404; }
    }

    /** 409: breaks a business rule (a MySQL trigger said no, or already served). */
    public static class Conflict extends ApiException {
        public Conflict(String message) { super(message); }
        @Override public int status() { return 409; }
    }

    /** 429: too many tries. */
    public static class TooManyRequests extends ApiException {
        public TooManyRequests(String message) { super(message); }
        @Override public int status() { return 429; }
    }

    /** 503: a feature that isn't switched on. */
    public static class Unavailable extends ApiException {
        public Unavailable(String message) { super(message); }
        @Override public int status() { return 503; }
    }
}
