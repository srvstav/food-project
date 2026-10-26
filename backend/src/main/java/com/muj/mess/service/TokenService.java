package com.muj.mess.service;

import com.fasterxml.jackson.databind.JsonNode;
import com.muj.mess.config.AppConfig;
import com.muj.mess.web.ApiException;
import com.muj.mess.web.Json;

import javax.crypto.Mac;
import javax.crypto.spec.SecretKeySpec;
import java.nio.charset.StandardCharsets;
import java.security.GeneralSecurityException;
import java.security.MessageDigest;
import java.util.Base64;
import java.util.Map;

/**
 * Session tokens: "<base64 {sid, exp}>.<HMAC-SHA256 signature>".
 * Only the server knows the secret, so nobody can forge a token for another student.
 * OOP: Single responsibility — this class only makes and checks tokens.
 */
public class TokenService {

    private final byte[] secret;

    public TokenService(byte[] secret) {
        this.secret = secret.clone(); // defensive copy: callers can't change our secret afterwards
    }

    public String make(int studentId) {
        long exp = System.currentTimeMillis() / 1000 + AppConfig.TOKEN_TTL_SECONDS;
        try {
            String body = b64(Json.MAPPER.writeValueAsBytes(Map.of("sid", studentId, "exp", exp)));
            return body + "." + sign(body);
        } catch (Exception e) {
            throw new IllegalStateException("Could not make a token", e);
        }
    }

    /** Returns the student id inside a valid "Bearer <token>" header, or throws 401. */
    public int studentIdFrom(String authorizationHeader) {
        String[] parts = authorizationHeader.split(" ", 2);
        if (parts.length != 2 || !parts[0].equalsIgnoreCase("bearer")) throw new ApiException.Unauthorized();
        String token = parts[1];
        int dot = token.lastIndexOf('.');
        if (dot < 1) throw new ApiException.Unauthorized();
        String body = token.substring(0, dot);
        String sig = token.substring(dot + 1);
        // Constant-time compare: an attacker can't guess the signature by timing our answer.
        if (!MessageDigest.isEqual(sig.getBytes(StandardCharsets.UTF_8), sign(body).getBytes(StandardCharsets.UTF_8))) {
            throw new ApiException.Unauthorized();
        }
        try {
            JsonNode payload = Json.MAPPER.readTree(Base64.getUrlDecoder().decode(body));
            if (payload.path("exp").asLong(0) < System.currentTimeMillis() / 1000) throw new ApiException.Unauthorized();
            return payload.path("sid").asInt();
        } catch (ApiException e) {
            throw e;
        } catch (Exception e) {
            throw new ApiException.Unauthorized();
        }
    }

    /** HMAC of any text with our secret, also used to store demo codes hashed. */
    String sign(String text) { // OOP: package-private (no modifier) — visible only inside com.muj.mess.service
        try {
            Mac mac = Mac.getInstance("HmacSHA256");
            mac.init(new SecretKeySpec(secret, "HmacSHA256"));
            return b64(mac.doFinal(text.getBytes(StandardCharsets.UTF_8)));
        } catch (GeneralSecurityException e) {
            throw new IllegalStateException(e);
        }
    }

    private static String b64(byte[] bytes) {
        return Base64.getUrlEncoder().withoutPadding().encodeToString(bytes);
    }
}
