package com.muj.mess.web;

import com.fasterxml.jackson.databind.DeserializationFeature;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.fasterxml.jackson.databind.SerializationFeature;
import com.fasterxml.jackson.datatype.jsr310.JavaTimeModule;

/**
 * One shared JSON converter (Jackson) for the whole app.
 * OOP: final class + private constructor — a utility class: can't be extended or created, only used statically.
 */
public final class Json {

    // Dates go out as "2026-10-27", not as numbers; unknown fields from the browser are ignored.
    public static final ObjectMapper MAPPER = new ObjectMapper()
            .registerModule(new JavaTimeModule())
            .disable(SerializationFeature.WRITE_DATES_AS_TIMESTAMPS)
            .disable(DeserializationFeature.FAIL_ON_UNKNOWN_PROPERTIES);

    private Json() {}
}
