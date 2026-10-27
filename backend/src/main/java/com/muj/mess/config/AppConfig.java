package com.muj.mess.config;
// Hello
import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.time.LocalDate;
import java.time.LocalDateTime;
import java.time.ZoneId;
import java.util.Base64;
import java.util.HashMap;
import java.util.List;
import java.util.Map;
import java.util.regex.Matcher;
import java.util.regex.Pattern;

/**
 * Every setting the app needs, read once at start-up.
 *
 * OOP: Record — a special kind of class for plain data. Java writes the constructor,
 * the getters (dbHost(), dbPort() …), equals(), hashCode() and toString() for us.
 * OOP: Immutability — a record's fields are final, so settings can't change while the app runs.
 */
public record AppConfig(
        String dbHost,
        int dbPort,
        String dbUser,
        String dbPassword,
        String dbName,
        String dbSslCa,          // null = no TLS (local MySQL)
        byte[] tokenSecret,
        String staffPin,
        List<String> allowedOrigins,
        int port,
        Path siteDir) {

    // OOP: static final constants — belong to the class, not to any one object, and never change.
    public static final ZoneId IST = ZoneId.of("Asia/Kolkata"); // cloud servers run on UTC; the mess runs on India time
    public static final int TOKEN_TTL_SECONDS = 7 * 24 * 3600;
    public static final int BOOKING_DAYS_AHEAD = 7;
    public static final int MAX_PAUSE_DAYS = 60;

    /**
     * OOP: Compact constructor — runs before the record is built, so a bad setting fails fast
     * and an AppConfig object can never exist in an invalid state.
     */
    public AppConfig {
        if (staffPin == null || staffPin.length() < 6) {
            throw new IllegalStateException("STAFF_PIN must be at least 6 characters");
        }
        allowedOrigins = List.copyOf(allowedOrigins); // defensive copy: nobody outside can change our list
    }

    /** OOP: static method — called on the class itself (AppConfig.today()), no object needed. */
    public static LocalDate today() {
        return LocalDate.now(IST);
    }

    public static LocalDateTime now() {
        return LocalDateTime.now(IST);
    }

    /**
     * OOP: Static factory method — a named way to build an object (instead of "new AppConfig(...)").
     * Reads backend/.env (written by setup.bat), then real environment variables win over the file.
     */
    public static AppConfig load(Path backendDir) {
        Map<String, String> env = new HashMap<>(readEnvFile(backendDir.resolve(".env")));
        env.putAll(System.getenv());

        // On Render every setting arrives packed in one base64 JSON value (made by setup_cloud.bat).
        String packed = env.get("MESS_SETTINGS");
        if (packed != null && !packed.isBlank()) {
            unpackSettings(packed).forEach(env::putIfAbsent);
        }

        return new AppConfig(
                env.getOrDefault("DB_HOST", "127.0.0.1"),
                Integer.parseInt(env.getOrDefault("DB_PORT", "3306")),
                required(env, "DB_USER"),
                required(env, "DB_PASSWORD"),
                env.getOrDefault("DB_NAME", "mess"),
                sslCaPath(env),
                required(env, "TOKEN_SECRET").getBytes(StandardCharsets.UTF_8),
                required(env, "STAFF_PIN"),
                List.of(env.getOrDefault("ALLOWED_ORIGINS", "*").split("\\s*,\\s*")),
                Integer.parseInt(env.getOrDefault("PORT", "8000")),
                backendDir.toAbsolutePath().getParent().resolve("docs"));
    }

    // OOP: private methods — Encapsulation. Helpers used only inside this class are hidden from everyone else.
    private static String required(Map<String, String> env, String name) {
        String value = env.get(name);
        if (value == null || value.isBlank()) {
            throw new IllegalStateException("Missing setting " + name + ". Run setup first (setup.bat / python setup.py local).");
        }
        return value;
    }

    /** Cloud MySQL needs TLS. Accept a file path, or the PEM text itself (handy on Render). */
    private static String sslCaPath(Map<String, String> env) {
        if (env.get("DB_SSL_CA") != null) return env.get("DB_SSL_CA");
        String pem = env.get("DB_SSL_CA_PEM");
        if (pem == null || pem.isBlank()) return null;
        try {
            Path file = Files.createTempFile("mess-ca", ".pem");
            Files.writeString(file, pem.replace("\\n", "\n"));
            return file.toString();
        } catch (IOException e) {
            throw new IllegalStateException("Could not write the CA certificate", e);
        }
    }

    /** Reads KEY=value lines; # starts a comment. Missing file = no settings from it. */
    private static Map<String, String> readEnvFile(Path file) {
        Map<String, String> out = new HashMap<>();
        if (!Files.exists(file)) return out;
        try {
            for (String line : Files.readAllLines(file, StandardCharsets.UTF_8)) {
                line = line.strip();
                int eq = line.indexOf('=');
                if (line.isEmpty() || line.startsWith("#") || eq < 1) continue;
                String value = line.substring(eq + 1).strip();
                if (value.length() >= 2 && (value.startsWith("\"") && value.endsWith("\"")
                        || value.startsWith("'") && value.endsWith("'"))) {
                    value = value.substring(1, value.length() - 1);
                }
                out.put(line.substring(0, eq).strip(), value);
            }
        } catch (IOException e) {
            throw new IllegalStateException("Could not read " + file, e);
        }
        return out;
    }

    // The packed value is a flat JSON object of strings and numbers, e.g. {"DB_HOST":"x","DB_PORT":12345}.
    private static final Pattern PAIR = Pattern.compile("\"([A-Z_]+)\"\\s*:\\s*(\"((?:[^\"\\\\]|\\\\.)*)\"|[-0-9.]+)");

    private static Map<String, String> unpackSettings(String packed) {
        String json = new String(Base64.getDecoder().decode(packed.strip()), StandardCharsets.UTF_8);
        Map<String, String> out = new HashMap<>();
        Matcher m = PAIR.matcher(json);
        while (m.find()) {
            String value = m.group(3) != null
                    ? m.group(3).replace("\\n", "\n").replace("\\\"", "\"").replace("\\\\", "\\")
                    : m.group(2);
            out.put(m.group(1), value);
        }
        return out;
    }

    /** Never print the password or the token secret. */
    @Override
    public String toString() { // OOP: Method overriding — replaces the toString() the record made for us.
        return "AppConfig[db=" + dbUser + "@" + dbHost + ":" + dbPort + "/" + dbName + ", port=" + port + "]";
    }
}
