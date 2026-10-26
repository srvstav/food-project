package com.muj.mess.web;

/**
 * One API endpoint: takes a request, returns the object to send back as JSON.
 * OOP: Functional interface — every route is a lambda like  req -> Map.of("status", "ok").
 * OOP: Abstraction — the server only knows "an Endpoint", never which controller it came from.
 */
@FunctionalInterface
public interface Endpoint {
    Object handle(ApiRequest req) throws Exception;
}
