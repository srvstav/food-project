package com.muj.mess.repository;

import java.sql.Connection;
import java.sql.SQLException;
import java.util.List;
import java.util.Map;

/** SQL for messes, meal slots and dishes. OOP: Inheritance from BaseRepository. */
public class MenuRepository extends BaseRepository {

    public List<Map<String, Object>> menu(Connection conn) throws SQLException {
        return queryAll(conn, "SELECT m.id AS mess_id, m.name AS mess, s.id AS slot_id, s.code AS slot_code, "
                + "s.name AS slot, TIME_FORMAT(s.starts_at, '%H:%i') AS starts_at, "
                + "TIME_FORMAT(s.ends_at, '%H:%i') AS ends_at, i.dish "
                + "FROM menu_items i JOIN messes m ON m.id = i.mess_id JOIN meal_slots s ON s.id = i.slot_id "
                + "ORDER BY s.id, m.id, i.id");
    }

    public boolean slotExists(Connection conn, int slotId) throws SQLException {
        return exists(conn, "SELECT 1 FROM meal_slots WHERE id = ?", slotId);
    }

    public boolean messExists(Connection conn, int messId) throws SQLException {
        return exists(conn, "SELECT 1 FROM messes WHERE id = ?", messId);
    }
}
