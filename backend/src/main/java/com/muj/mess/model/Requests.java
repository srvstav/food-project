package com.muj.mess.model;

import com.fasterxml.jackson.annotation.JsonProperty;

import java.time.LocalDate;

/**
 * The JSON bodies the browser sends. Each one is a record that implements Validatable.
 *
 * OOP: Polymorphism — all seven types are different, but each is also "a Validatable",
 * and each one's validate() does its own checks (method overriding).
 * OOP: Nested types — grouped inside Requests because they belong together (Requests.Booking …).
 */
public final class Requests {

    private Requests() {} // OOP: private constructor — this class is only a namespace, nobody can create one

    public record Phone(String phone) implements Validatable {
        @Override
        public void validate() {
            requirePhone(phone);
        }
    }

    public record DemoVerify(String phone, String otp) implements Validatable {
        @Override
        public void validate() {
            requirePhone(phone);
            require(otp != null && otp.matches("\\d{6}"), "The code is 6 digits");
        }
    }

    public record Login(@JsonProperty("id_token") String idToken) implements Validatable {
        @Override
        public void validate() {
            require(idToken != null && idToken.length() >= 20 && idToken.length() <= 4096, "Not a login token");
        }
    }

    /** messId == null means "skip this meal". */
    public record BookMeal(@JsonProperty("meal_date") LocalDate mealDate,
                           @JsonProperty("slot_id") Integer slotId,
                           @JsonProperty("mess_id") Integer messId) implements Validatable {
        @Override
        public void validate() {
            require(mealDate != null, "Pick a date");
            requireId(slotId, "meal");
            if (messId != null) requireId(messId, "mess");
        }

        public MealStatus status() {
            return messId != null ? MealStatus.BOOKED : MealStatus.SKIPPED;
        }
    }

    public record Pause(@JsonProperty("from_date") LocalDate fromDate,
                        @JsonProperty("to_date") LocalDate toDate) implements Validatable {
        @Override
        public void validate() {
            require(fromDate != null && toDate != null, "Pick both dates");
            require(!toDate.isBefore(fromDate), "Return date must be on or after the leaving date");
        }
    }

    public record Serve(String phone,
                        @JsonProperty("mess_id") Integer messId,
                        @JsonProperty("slot_id") Integer slotId) implements Validatable {
        @Override
        public void validate() {
            requirePhone(phone);
            requireId(messId, "mess");
            requireId(slotId, "meal");
        }
    }

    public record CloseMeal(@JsonProperty("meal_date") LocalDate mealDate,
                            @JsonProperty("slot_id") Integer slotId) implements Validatable {
        @Override
        public void validate() {
            require(mealDate != null, "Pick a date");
            requireId(slotId, "meal");
        }
    }
}
