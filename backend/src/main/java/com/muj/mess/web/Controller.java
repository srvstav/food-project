package com.muj.mess.web;

/**
 * A group of related endpoints (login, student, staff, dashboard).
 * OOP: Interface — each controller class "implements Controller" and adds its own routes.
 * OOP: Polymorphism — Main keeps a List<Controller> and calls register() on each,
 *      without caring which concrete class it is.
 */
public interface Controller {
    void register(Router router);
}
