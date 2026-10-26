package com.muj.mess.service;

import com.muj.mess.web.ApiException;
import org.junit.jupiter.api.Test;

import java.nio.charset.StandardCharsets;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertThrows;

class TokenServiceTest {

    private final TokenService tokens = new TokenService("test-secret".getBytes(StandardCharsets.UTF_8));

    @Test
    void aTokenGivesBackTheSameStudent() {
        assertEquals(42, tokens.studentIdFrom("Bearer " + tokens.make(42)));
    }

    @Test
    void aChangedTokenIsRefused() {
        String token = tokens.make(42);
        String forged = tokens.make(7).split("\\.")[0] + "." + token.split("\\.")[1]; // body of 7, signature of 42
        assertThrows(ApiException.Unauthorized.class, () -> tokens.studentIdFrom("Bearer " + forged));
    }

    @Test
    void aTokenFromAnotherSecretIsRefused() {
        TokenService other = new TokenService("other".getBytes(StandardCharsets.UTF_8));
        assertThrows(ApiException.Unauthorized.class, () -> tokens.studentIdFrom("Bearer " + other.make(42)));
    }

    @Test
    void noTokenIsRefused() {
        assertThrows(ApiException.Unauthorized.class, () -> tokens.studentIdFrom(""));
    }
}
