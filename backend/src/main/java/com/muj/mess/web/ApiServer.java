package com.muj.mess.web;

import com.muj.mess.config.AppConfig;
import com.sun.net.httpserver.Headers;
import com.sun.net.httpserver.HttpExchange;
import com.sun.net.httpserver.HttpHandler;
import com.sun.net.httpserver.HttpServer;

import java.io.IOException;
import java.io.OutputStream;
import java.net.InetSocketAddress;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.sql.SQLException;
import java.time.LocalTime;
import java.util.List;
import java.util.Map;
import java.util.Optional;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;
import java.util.logging.Level;
import java.util.logging.Logger;

/**
 * The web server: sends each request to its Endpoint, turns the answer into JSON,
 * turns errors into the right status code, and serves the website from docs/.
 *
 * OOP: Interface implementation — "implements HttpHandler", Java's own interface; the JDK's HttpServer
 *      calls our handle() method for every request (we plug our object into Java's library).
 */
public class ApiServer implements HttpHandler {

    private static final Logger LOG = Logger.getLogger(ApiServer.class.getName());
    private static final int MYSQL_SIGNAL = 1644;   // SIGNAL SQLSTATE '45000' inside a trigger/procedure
    private static final int MYSQL_DUPLICATE = 1062; // UNIQUE key broken

    private static final Map<String, String> CONTENT_TYPES = Map.of(
            "html", "text/html; charset=utf-8", "js", "text/javascript; charset=utf-8",
            "css", "text/css; charset=utf-8", "json", "application/json", "webp", "image/webp",
            "png", "image/png", "jpg", "image/jpeg", "svg", "image/svg+xml", "ico", "image/x-icon");

    private final Router router;
    private final Path siteDir;
    private final List<String> allowedOrigins;

    public ApiServer(Router router, Path siteDir, List<String> allowedOrigins) {
        this.router = router;
        this.siteDir = siteDir.toAbsolutePath().normalize();
        this.allowedOrigins = allowedOrigins;
    }

    public void start(int port, String host) throws IOException {
        HttpServer server = HttpServer.create(new InetSocketAddress(host, port), 0);
        server.createContext("/", this); // OOP: "this" — pass this very object as the handler
        ExecutorService pool = Executors.newFixedThreadPool(16); // 16 requests can run at the same time
        server.setExecutor(pool);
        server.start();
    }

    @Override // OOP: Method overriding — this is HttpHandler's method, given our own body
    public void handle(HttpExchange ex) throws IOException {
        try (ex) {
            addCorsHeaders(ex);
            String method = ex.getRequestMethod();
            String path = ex.getRequestURI().getPath();

            if (method.equals("OPTIONS")) { // browser asking "may I call you?" before a POST
                ex.sendResponseHeaders(204, -1);
                return;
            }
            if (path.equals("/admin")) {
                ex.getResponseHeaders().set("Location", "/dashboard.html");
                ex.sendResponseHeaders(307, -1);
                return;
            }
            Optional<Endpoint> endpoint = router.find(method, path);
            if (endpoint.isPresent()) {
                long started = System.nanoTime();
                answer(ex, endpoint.get());
                // Live request log in the server window, so the backend's work is visible during the demo.
                System.out.printf("%s  %-4s %-20s → %d  (%d ms)%n", LocalTime.now(AppConfig.IST).withNano(0),
                        method, path, ex.getResponseCode(), (System.nanoTime() - started) / 1_000_000);
            } else if (router.knows(path)) {
                sendJson(ex, 405, Map.of("detail", "Method not allowed"));
            } else {
                serveFile(ex, path);
            }
        } catch (IOException e) {
            LOG.log(Level.FINE, "client went away", e);
        }
    }

    /** Runs the endpoint. OOP: Exception handling — each catch turns one kind of failure into an HTTP answer. */
    private void answer(HttpExchange ex, Endpoint endpoint) throws IOException {
        try {
            sendJson(ex, 200, endpoint.handle(new ApiRequest(ex))); // OOP: Polymorphism — any controller's lambda
        } catch (ApiException e) {
            sendJson(ex, e.status(), Map.of("detail", e.getMessage())); // each subclass knows its own status
        } catch (SQLException e) {
            if (e.getErrorCode() == MYSQL_SIGNAL) { // a business rule in MySQL said no — not a crash
                sendJson(ex, 409, Map.of("detail", e.getMessage()));
            } else if (e.getErrorCode() == MYSQL_DUPLICATE) {
                sendJson(ex, 409, Map.of("detail", "That is already saved"));
            } else {
                LOG.log(Level.SEVERE, "database error", e);
                sendJson(ex, 503, Map.of("detail", "Database is unavailable, try again"));
            }
        } catch (Exception e) {
            LOG.log(Level.SEVERE, "unexpected error", e);
            sendJson(ex, 500, Map.of("detail", "Something went wrong"));
        }
    }

    private void addCorsHeaders(HttpExchange ex) {
        String origin = ex.getRequestHeaders().getFirst("Origin");
        Headers h = ex.getResponseHeaders();
        if (allowedOrigins.contains("*")) {
            h.set("Access-Control-Allow-Origin", "*");
        } else if (origin != null && allowedOrigins.contains(origin)) {
            h.set("Access-Control-Allow-Origin", origin);
            h.set("Vary", "Origin");
        }
        h.set("Access-Control-Allow-Methods", "GET, POST");
        h.set("Access-Control-Allow-Headers", "Authorization, Content-Type, X-Staff-Pin");
    }

    private static void sendJson(HttpExchange ex, int status, Object body) throws IOException {
        byte[] bytes = Json.MAPPER.writeValueAsBytes(body);
        ex.getResponseHeaders().set("Content-Type", "application/json");
        send(ex, status, bytes);
    }

    private static void send(HttpExchange ex, int status, byte[] bytes) throws IOException {
        ex.sendResponseHeaders(status, bytes.length == 0 ? -1 : bytes.length);
        try (OutputStream out = ex.getResponseBody()) {
            out.write(bytes);
        }
    }

    /** The same site GitHub Pages serves, so the whole system also runs offline from one laptop. */
    private void serveFile(HttpExchange ex, String urlPath) throws IOException {
        if (!ex.getRequestMethod().equals("GET") && !ex.getRequestMethod().equals("HEAD")) {
            sendJson(ex, 404, Map.of("detail", "Not Found"));
            return;
        }
        Path file = siteDir.resolve(urlPath.substring(1)).normalize();
        if (Files.isDirectory(file)) file = file.resolve("index.html");
        // Security: normalize() + startsWith() blocks "/../backend/.env" style paths from leaving docs/.
        if (!file.startsWith(siteDir) || !Files.isRegularFile(file)) {
            ex.getResponseHeaders().set("Content-Type", "text/plain; charset=utf-8");
            send(ex, 404, "Not Found".getBytes(StandardCharsets.UTF_8));
            return;
        }
        String name = file.getFileName().toString();
        String ext = name.substring(name.lastIndexOf('.') + 1).toLowerCase();
        ex.getResponseHeaders().set("Content-Type", CONTENT_TYPES.getOrDefault(ext, "application/octet-stream"));
        if (ext.equals("html") || ext.equals("js") || ext.equals("css")) {
            ex.getResponseHeaders().set("Cache-Control", "no-cache"); // updates show at once
        }
        send(ex, 200, ex.getRequestMethod().equals("HEAD") ? new byte[0] : Files.readAllBytes(file));
    }
}
