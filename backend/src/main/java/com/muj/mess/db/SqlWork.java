package com.muj.mess.db;

import java.sql.Connection;
import java.sql.SQLException;

/**
 * One piece of database work that runs inside a transaction.
 *
 * OOP: Interface + Generics — <T> is the type of the result, chosen by whoever uses it
 * (SqlWork<Boolean>, SqlWork<Map<...>> …), so one interface fits every kind of query.
 * OOP: Functional interface — it has exactly one abstract method, so a lambda can stand in for it:
 *     db.inTransaction(conn -> studentRepo.findByPhone(conn, phone))
 */
@FunctionalInterface
public interface SqlWork<T> {
    T run(Connection conn) throws SQLException;
}
