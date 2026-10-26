package com.muj.mess.model;

/**
 * Anything that arrives from the browser and must be checked before we trust it.
 *
 * OOP: Interface — a contract. Every request class "implements Validatable" and so must have validate().
 * OOP: Abstraction — the web layer calls body.validate() without knowing which request it is.
 */
public interface Validatable {

    /** Throws an IllegalArgumentException with a friendly message when the input is wrong. */
    void validate();

    // OOP: default method — an interface can also give shared code that every implementer gets for free.
    default void require(boolean ok, String message) {
        if (!ok) throw new IllegalArgumentException(message);
    }

    /** 10-digit Indian mobile number, starting with 6, 7, 8 or 9. */
    default void requirePhone(String phone) {
        require(phone != null && phone.matches("[6-9]\\d{9}"), "Enter a 10-digit mobile number");
    }

    /** Meal slot and mess ids are small positive numbers. */
    default void requireId(Integer id, String what) {
        require(id != null && id >= 1 && id <= 255, "Unknown " + what);
    }
}
