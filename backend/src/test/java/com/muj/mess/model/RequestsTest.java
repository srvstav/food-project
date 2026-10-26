package com.muj.mess.model;

import org.junit.jupiter.api.Test;

import java.time.LocalDate;

import static org.junit.jupiter.api.Assertions.assertDoesNotThrow;
import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertThrows;

class RequestsTest {

    @Test
    void phoneMustBeTenDigitsStartingSixToNine() {
        assertDoesNotThrow(() -> new Requests.Phone("9876543210").validate());
        assertThrows(IllegalArgumentException.class, () -> new Requests.Phone("1234567890").validate());
        assertThrows(IllegalArgumentException.class, () -> new Requests.Phone("98765").validate());
    }

    @Test
    void pauseCannotEndBeforeItStarts() {
        LocalDate d = LocalDate.of(2026, 10, 27);
        assertThrows(IllegalArgumentException.class, () -> new Requests.Pause(d, d.minusDays(1)).validate());
        assertDoesNotThrow(() -> new Requests.Pause(d, d).validate());
    }

    @Test
    void noMessMeansSkipped() {
        LocalDate d = LocalDate.of(2026, 10, 27);
        assertEquals(MealStatus.SKIPPED, new Requests.BookMeal(d, 1, null).status());
        assertEquals(MealStatus.BOOKED, new Requests.BookMeal(d, 1, 2).status());
    }

    @Test
    void bookingKnowsWhereItWasMade() {
        Booking b = new Booking(1, "BluDove", MealStatus.BOOKED);
        assertEquals(true, b.isBookedAt(1));
        assertEquals(false, b.isBookedAt(2));
        assertEquals("skipped", new Booking(null, null, MealStatus.SKIPPED).label());
    }
}
