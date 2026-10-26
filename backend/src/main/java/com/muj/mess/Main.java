package com.muj.mess;

import com.muj.mess.config.AppConfig;
import com.muj.mess.db.Database;
import com.muj.mess.repository.BookingRepository;
import com.muj.mess.repository.DashboardRepository;
import com.muj.mess.repository.MealRepository;
import com.muj.mess.repository.MenuRepository;
import com.muj.mess.repository.StudentRepository;
import com.muj.mess.service.AuthService;
import com.muj.mess.service.DashboardService;
import com.muj.mess.service.StaffService;
import com.muj.mess.service.StudentService;
import com.muj.mess.service.TokenService;
import com.muj.mess.web.ApiServer;
import com.muj.mess.web.Controller;
import com.muj.mess.web.Router;
import com.muj.mess.web.controller.AuthController;
import com.muj.mess.web.controller.DashboardController;
import com.muj.mess.web.controller.StaffController;
import com.muj.mess.web.controller.StudentController;

import java.nio.file.Files;
import java.nio.file.Path;
import java.util.List;

/**
 * Start here. Builds every object once and wires them together, then starts the server.
 *
 * OOP: Dependency Injection (by hand) — each object gets the objects it needs through its constructor.
 *      Nothing inside the app calls "new" on a database or a service by itself; Main decides.
 * OOP: Objects — every "new X(...)" below creates an object (an instance) of class X.
 */
public class Main {

    public static void main(String[] args) throws Exception {
        Path backendDir = Files.isDirectory(Path.of("backend")) ? Path.of("backend") : Path.of("."); // run from repo root or backend/
        AppConfig config = AppConfig.load(backendDir);

        // 1. Database layer
        Database db = new Database(config);

        // 2. Repositories (SQL) — all extend BaseRepository
        StudentRepository studentRepo = new StudentRepository();
        MenuRepository menuRepo = new MenuRepository();
        BookingRepository bookingRepo = new BookingRepository();
        MealRepository mealRepo = new MealRepository();
        DashboardRepository dashboardRepo = new DashboardRepository();

        // 3. Services (business rules)
        TokenService tokens = new TokenService(config.tokenSecret());
        AuthService auth = new AuthService(db, studentRepo, tokens, config.staffPin());
        StudentService students = new StudentService(db, studentRepo, menuRepo, bookingRepo);
        StaffService staff = new StaffService(db, studentRepo, menuRepo, bookingRepo, mealRepo);
        DashboardService dashboard = new DashboardService(db, dashboardRepo, mealRepo, studentRepo);

        // 4. Controllers (HTTP endpoints)
        // OOP: Polymorphism — four different classes stored as one type, List<Controller>.
        List<Controller> controllers = List.of(
                new AuthController(auth, students),
                new StudentController(auth, students),
                new StaffController(auth, staff),
                new DashboardController(dashboard, db, menuRepo));
        Router router = new Router();
        for (Controller c : controllers) {
            c.register(router); // each object runs its own version of register()
        }

        // 5. Server
        String host = System.getenv().getOrDefault("HOST", "127.0.0.1");
        new ApiServer(router, config.siteDir(), config.allowedOrigins()).start(config.port(), host);
        System.out.println("MUJ Mess (Java) is running on http://localhost:" + config.port());
        System.out.println("  Student site : http://localhost:" + config.port());
        System.out.println("  Live board   : http://localhost:" + config.port() + "/dashboard.html");
        System.out.println("  Staff counter: http://localhost:" + config.port() + "/staff.html");
        System.out.println("Using " + config + ". Press Ctrl+C to stop.");
    }
}
