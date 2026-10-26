package com.muj.mess.web.controller;

import com.muj.mess.config.AppConfig;
import com.muj.mess.db.Database;
import com.muj.mess.repository.MenuRepository;
import com.muj.mess.service.DashboardService;
import com.muj.mess.web.ApiException;
import com.muj.mess.web.Controller;
import com.muj.mess.web.Router;

import java.util.Map;

/** Public endpoints: health check, today's forecast and the live board. */
public class DashboardController implements Controller {

    private final DashboardService dashboard;
    private final Database db;
    private final MenuRepository menu;

    public DashboardController(DashboardService dashboard, Database db, MenuRepository menu) {
        this.dashboard = dashboard;
        this.db = db;
        this.menu = menu;
    }

    @Override
    public void register(Router r) {
        r.get("/health", req -> {
            db.inTransaction(conn -> menu.slotExists(conn, 1)); // proves the database answers, not just the API
            return Map.of("status", "ok", "today", AppConfig.today().toString());
        });

        r.get("/stats/today", req -> Map.of("meal_date", AppConfig.today(), "forecast", dashboard.forecast(AppConfig.today())));

        r.get("/admin/live", req -> dashboard.live(limit(req.query("limit"))));
    }

    private static int limit(String value) {
        if (value == null) return 25;
        try {
            int n = Integer.parseInt(value);
            if (n >= 1 && n <= 100) return n;
        } catch (NumberFormatException ignored) {
            // falls through to the error below
        }
        throw new ApiException.BadRequest("limit must be 1 to 100");
    }
}
