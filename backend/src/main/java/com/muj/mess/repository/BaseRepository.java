package com.muj.mess.repository;

import java.math.BigDecimal;
import java.sql.Connection;
import java.sql.PreparedStatement;
import java.sql.ResultSet;
import java.sql.ResultSetMetaData;
import java.sql.SQLException;
import java.sql.Types;
import java.time.LocalDate;
import java.time.LocalDateTime;
import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.Optional;

/**
 * Shared JDBC code for every repository.
 *
 * OOP: Abstract class — you can't write "new BaseRepository()". It exists only to be extended.
 * OOP: Inheritance — StudentRepository, BookingRepository … "extends BaseRepository" and inherit
 *      queryOne(), queryAll() and execute(), so no repository repeats the JDBC code (DRY).
 * OOP: protected — subclasses can use these helpers; the rest of the app cannot.
 *
 * Security: every query uses PreparedStatement with ? placeholders, never string-built SQL,
 * so a value typed by a user can't change the SQL (no SQL injection).
 */
public abstract class BaseRepository {

    /**
     * Turns one ResultSet row into an object of type T.
     * OOP: Nested generic functional interface — each repository passes a lambda that builds its own type.
     */
    @FunctionalInterface
    protected interface RowMapper<T> {
        T map(ResultSet rs) throws SQLException;
    }

    /** First row mapped by the mapper, or Optional.empty() when there is none. */
    protected <T> Optional<T> queryOne(Connection conn, String sql, RowMapper<T> mapper, Object... params)
            throws SQLException {
        try (PreparedStatement ps = prepare(conn, sql, params); ResultSet rs = ps.executeQuery()) {
            return rs.next() ? Optional.of(mapper.map(rs)) : Optional.empty();
        }
    }

    /** OOP: Method overloading — same name as the next method, different parameters: no mapper → rows as maps. */
    protected List<Map<String, Object>> queryAll(Connection conn, String sql, Object... params) throws SQLException {
        return queryAll(conn, sql, BaseRepository::toMap, params);
    }

    protected <T> List<T> queryAll(Connection conn, String sql, RowMapper<T> mapper, Object... params)
            throws SQLException {
        List<T> rows = new ArrayList<>();
        try (PreparedStatement ps = prepare(conn, sql, params); ResultSet rs = ps.executeQuery()) {
            while (rs.next()) rows.add(mapper.map(rs));
        }
        return rows;
    }

    protected boolean exists(Connection conn, String sql, Object... params) throws SQLException {
        return queryOne(conn, sql, rs -> true, params).isPresent();
    }

    /** INSERT / UPDATE / CALL. Returns how many rows changed. */
    protected int execute(Connection conn, String sql, Object... params) throws SQLException {
        try (PreparedStatement ps = prepare(conn, sql, params)) {
            return ps.executeUpdate();
        }
    }

    // OOP: private — only this class needs to know how parameters are bound.
    private static PreparedStatement prepare(Connection conn, String sql, Object... params) throws SQLException {
        PreparedStatement ps = conn.prepareStatement(sql);
        for (int i = 0; i < params.length; i++) {
            ps.setObject(i + 1, params[i]); // ? number i+1 gets params[i]; the driver escapes it safely
        }
        return ps;
    }

    /** One row as column → value, with values the browser can read as JSON. */
    protected static Map<String, Object> toMap(ResultSet rs) throws SQLException {
        ResultSetMetaData meta = rs.getMetaData();
        Map<String, Object> row = new LinkedHashMap<>();
        for (int i = 1; i <= meta.getColumnCount(); i++) {
            row.put(meta.getColumnLabel(i), jsonValue(rs, i, meta.getColumnType(i)));
        }
        return row;
    }

    private static Object jsonValue(ResultSet rs, int i, int sqlType) throws SQLException {
        // Dates are read as LocalDate so the JVM's own time zone can't shift them by a day.
        Object value = switch (sqlType) {
            case Types.DATE -> rs.getObject(i, LocalDate.class);
            case Types.TIMESTAMP -> rs.getObject(i, LocalDateTime.class);
            default -> rs.getObject(i);
        };
        if (value == null) return null;
        // OOP: Pattern matching with instanceof — checks the runtime type and casts in one step.
        if (value instanceof BigDecimal d) { // SUM() and money columns come back as BigDecimal
            return d.stripTrailingZeros().scale() <= 0 ? (Object) d.longValue() : d.doubleValue();
        }
        if (value instanceof LocalDate || value instanceof LocalDateTime || value instanceof java.sql.Time) {
            return value.toString(); // "2026-10-27", "2026-10-27T08:15", "08:15:00"
        }
        return value;
    }
}
