package com.muj.mess.web;

import java.util.HashMap;
import java.util.Map;
import java.util.Optional;

/**
 * Remembers which Endpoint answers which "METHOD /path".
 * OOP: Composition — the Router HAS-A Map of endpoints; ApiServer HAS-A Router.
 */
public class Router {

    private final Map<String, Endpoint> routes = new HashMap<>(); // "GET /menu" -> endpoint

    public void get(String path, Endpoint endpoint) {
        add(HttpMethod.GET, path, endpoint);
    }

    public void post(String path, Endpoint endpoint) {
        add(HttpMethod.POST, path, endpoint);
    }

    private void add(HttpMethod method, String path, Endpoint endpoint) {
        if (routes.putIfAbsent(method + " " + path, endpoint) != null) {
            throw new IllegalStateException("Route registered twice: " + method + " " + path); // fail fast
        }
    }

    public Optional<Endpoint> find(String method, String path) {
        return Optional.ofNullable(routes.get(method + " " + path));
    }

    /** True if any method is registered for this path (used to answer CORS preflight requests). */
    public boolean knows(String path) {
        for (HttpMethod m : HttpMethod.values()) {
            if (routes.containsKey(m + " " + path)) return true;
        }
        return false;
    }
}
