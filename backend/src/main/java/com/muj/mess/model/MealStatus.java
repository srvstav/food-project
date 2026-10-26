package com.muj.mess.model;

/**
 * What a student chose for one meal.
 *
 * OOP: Enum — a fixed set of named objects. A status can only ever be BOOKED or SKIPPED,
 * never a typo like "bookd". Enums can carry fields and methods, like any class.
 */
public enum MealStatus {
    BOOKED("booked"),
    SKIPPED("skipped");

    private final String dbValue; // the word stored in the bookings.status column

    MealStatus(String dbValue) { // OOP: enum constructor — runs once for each constant above
        this.dbValue = dbValue;
    }

    public String dbValue() {
        return dbValue;
    }

    /** Reads the database word back into an enum constant. */
    public static MealStatus fromDb(String value) {
        for (MealStatus s : values()) {
            if (s.dbValue.equals(value)) return s;
        }
        throw new IllegalArgumentException("Unknown meal status: " + value);
    }
}
