package com.muj.mess.model;

/**
 * One row of the students table (the parts the API needs).
 * OOP: Record — immutable data class; Java generates the constructor and getters id(), fullName(), status().
 */
public record Student(int id, String fullName, String status) {

    // OOP: Behaviour belongs with the data — the Student decides what "active" means.
    public boolean isActive() {
        return "active".equals(status);
    }
}
