package com.muj.mess.web;

import com.fasterxml.jackson.core.JsonProcessingException;
import com.muj.mess.model.Validatable;
import com.sun.net.httpserver.HttpExchange;

import java.io.IOException;
import java.io.InputStream;
import java.net.URLDecoder;
import java.nio.charset.StandardCharsets;
import java.util.HashMap;
import java.util.Map;

/**
 * The parts of an HTTP request a controller needs: headers, query string, JSON body.
 *
 * OOP: Encapsulation — wraps Java's HttpExchange (a "wrapper" class). Controllers call simple methods
 *      like header("X-Staff-Pin") and never touch the raw exchange.
 */
public class ApiRequest {

    private static final int MAX_BODY_BYTES = 64 * 1024; // no request body needs more; stops huge uploads

    private final HttpExchange exchange;
    private final Map<String, String> query;

    public ApiRequest(HttpExchange exchange) {
        this.exchange = exchange;
        this.query = parseQuery(exchange.getRequestURI().getRawQuery());
    }

    /** A header value, or "" when it isn't there. */
    public String header(String name) {
        String value = exchange.getRequestHeaders().getFirst(name);
        return value == null ? "" : value;
    }

    /** A ?name=value from the URL, or null. */
    public String query(String name) {
        return query.get(name);
    }

    /** The caller's IP. Behind Render's proxy it arrives in X-Forwarded-For. */
    public String clientIp() {
        String forwarded = header("X-Forwarded-For");
        return forwarded.isBlank()
                ? exchange.getRemoteAddress().getAddress().getHostAddress()
                : forwarded.split(",")[0].strip();
    }

    /**
     * Reads the JSON body into the given record type, then checks it.
     * OOP: Bounded generics — <T extends Validatable> means "any type, as long as it is a Validatable",
     *      so we're allowed to call validate() on it. Polymorphism picks that type's own validate().
     */
    public <T extends Validatable> T body(Class<T> type) {
        T value;
        try (InputStream in = exchange.getRequestBody()) {
            byte[] bytes = in.readNBytes(MAX_BODY_BYTES + 1);
            if (bytes.length > MAX_BODY_BYTES) throw new ApiException.BadRequest("Request is too large");
            value = Json.MAPPER.readValue(bytes, type);
        } catch (JsonProcessingException e) {
            throw new ApiException.BadRequest("Check the form: some fields are missing or in the wrong format");
        } catch (IOException e) {
            throw new ApiException.BadRequest("Could not read the request");
        }
        if (value == null) throw new ApiException.BadRequest("Request body is empty");
        try {
            value.validate();
        } catch (IllegalArgumentException e) {
            throw new ApiException.BadRequest(e.getMessage()); // turn the record's message into a 400 for the browser
        }
        return value;
    }

    private static Map<String, String> parseQuery(String raw) {
        Map<String, String> out = new HashMap<>();
        if (raw == null || raw.isEmpty()) return out;
        for (String pair : raw.split("&")) {
            int eq = pair.indexOf('=');
            String key = eq < 0 ? pair : pair.substring(0, eq);
            String value = eq < 0 ? "" : pair.substring(eq + 1);
            out.put(URLDecoder.decode(key, StandardCharsets.UTF_8), URLDecoder.decode(value, StandardCharsets.UTF_8));
        }
        return out;
    }
}
