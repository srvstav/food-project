package com.muj.mess.model;

/**
 * A student's booking for one meal. messId and messName are null when the meal was skipped.
 * OOP: Composition — a Booking HAS-A MealStatus (an enum object) inside it.
 */
public record Booking(Integer messId, String messName, MealStatus status) {

    /** Did the student book this exact mess? (Used when staff serve someone.) */
    public boolean isBookedAt(int messId) {
        return status == MealStatus.BOOKED && this.messId != null && this.messId == messId;
    }

    /** What the staff screen shows: the mess name, or "skipped". */
    public String label() {
        return messName != null ? messName : status.dbValue();
    }
}
