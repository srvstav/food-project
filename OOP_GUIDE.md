# OOP Guide: learn the whole system for the viva

Read it top to bottom once (about 30 minutes). Then do the demo script at the end twice.

---

## 1. The 30-second pitch (say this first)

> "Our project is a mess booking system for MUJ. Students book which mess they'll eat at for each meal, so each kitchen cooks for the people who booked plus 30%, not for everyone. Staff mark who was served, and leftover food is given to NGOs. The backend is written in plain Java 17 without frameworks, so all the object-oriented design is our own code. It has three layers, controller, service and repository, and it talks to MySQL through JDBC. The frontend is an HTML and JavaScript website that calls our Java API."

## 2. The big picture

```
Browser ──HTTP + JSON──► ApiServer ──► Router ──► Controller ──► Service ──► Repository ──JDBC──► MySQL
 (docs/)                 (web/)        (web/)    (web/controller/) (service/)  (repository/)        (db/)
```

| Layer | Job | Example |
| --- | --- | --- |
| **Controller** | Reads the HTTP request, calls a service, returns the answer | `StudentController` gets `POST /bookings` |
| **Service** | The business rules | `StudentService.book()` checks "date must be within 7 days" |
| **Repository** | The SQL, and nothing else | `BookingRepository.upsert()` runs the `INSERT` |
| **Model** | The data objects passed between layers | `Student`, `Booking`, `MealStatus`, `Requests.BookMeal` |

**Why layers?** Each class has one job (Single Responsibility). If the database changes, only repositories change. If a rule changes, only a service changes.

`Main.java` creates every object once and hands each one what it needs. Start reading there.

## 3. Follow one request: a student books lunch

The browser sends `POST /bookings` with `{"meal_date":"2026-10-27","slot_id":2,"mess_id":1}` and the header `Authorization: Bearer <token>`.

1. **`ApiServer.handle()`**: Java's `HttpServer` calls this for every request, because `ApiServer implements HttpHandler`.
2. **`Router.find("POST", "/bookings")`** looks the route up in a `HashMap` and returns the `Endpoint` (a lambda).
3. The lambda in **`StudentController`** runs:
   - `me(req)` → `AuthService.requireStudent()` → `TokenService.studentIdFrom()` checks the token's HMAC signature and returns the student id, or throws `ApiException.Unauthorized`.
   - `req.body(Requests.BookMeal.class)`: **`ApiRequest`** turns the JSON into a `BookMeal` record (Jackson library), then calls `validate()` on it.
4. **`StudentService.book()`** checks the date window, then calls `db.inTransaction(conn -> ...)`.
5. **`Database.inTransaction()`** opens a connection, runs the lambda, and **commits**. If anything throws, it **rolls back**.
6. **`BookingRepository.upsert()`** runs a `PreparedStatement` with `?` placeholders.
7. In MySQL, a **trigger** checks whether the student has paused. If so it raises `SIGNAL SQLSTATE '45000'` (error code 1644).
8. Back in **`ApiServer.answer()`**: success → `200 {"status":"booked"}`. A trigger error → `SQLException` code 1644 → `409` with the trigger's message. An `ApiException` → its own `status()`.

If you can tell this story, you can answer most questions.

---

## 4. The four pillars, with our code

### 4.1 Encapsulation: hide the data, expose safe methods

**What it is:** fields are `private`, and other classes can only use the object through its public methods. The object protects its own state.

**Where:**
- `db/Database.java`: `url` and `props` (which hold the password) are `private final`. Nobody else can read the password. They can only call `inTransaction()`.
- `service/RateLimiter.java`: the `tries` map is private. The only way in is `tryAcquire()`, which is `synchronized` so two threads can't break the map.
- `web/ApiRequest.java` **wraps** Java's `HttpExchange`. Controllers call `header()`, `query()` and `body()` and never touch the raw exchange.
- `service/TokenService.java`: `this.secret = secret.clone()` is a **defensive copy**, so the caller can't change our secret later.

**Access modifiers we use:** `private` (only this class), package-private with no keyword (`TokenService.sign()`, only the `service` package), `protected` (`BaseRepository` helpers, only subclasses), `public` (everyone).

### 4.2 Inheritance: a child class reuses and extends a parent

**What it is:** `class B extends A` means B gets all of A's non-private members. It's an "is-a" relationship.

**Where (two real hierarchies):**

```
BaseRepository (abstract)                    RuntimeException (Java's)
 ├─ StudentRepository                          └─ ApiException (abstract)
 ├─ MenuRepository                                 ├─ BadRequest       → 400
 ├─ BookingRepository                              ├─ Unauthorized     → 401
 ├─ MealRepository                                 ├─ Forbidden        → 403
 └─ DashboardRepository                            ├─ NotFound         → 404
                                                   ├─ Conflict         → 409
                                                   ├─ TooManyRequests  → 429
                                                   └─ Unavailable      → 503
```

- `repository/BaseRepository.java` has `queryOne()`, `queryAll()`, `exists()` and `execute()`. Every repository inherits them, so no repository repeats the JDBC code (DRY).
- `web/ApiException.java`: each subclass calls `super(message)`, which runs the parent constructor.

### 4.3 Polymorphism: one call, many behaviours

**What it is:** the same method call does different things depending on the object's real class.

**Runtime polymorphism (method overriding):**
- `ApiServer.answer()` has `catch (ApiException e) { ... e.status() ... }`. It doesn't know whether it caught a `BadRequest` or a `Conflict`. Each subclass **overrides** `status()`, and Java calls the right one at runtime (dynamic dispatch). No if/else chain.
- `Main.java` keeps `List<Controller> controllers` holding four different classes, then calls `c.register(router)` on each. Each runs its own version.
- `ApiRequest.body()` calls `value.validate()`. Whether it's a `Phone`, a `Pause` or a `BookMeal`, its own `validate()` runs.
- `ApiServer.handle()` overrides `HttpHandler.handle()`, and `AppConfig.toString()` overrides the record's `toString()` (to hide the password).

**Compile-time polymorphism (method overloading):**
- `BaseRepository.queryAll(conn, sql, params...)` and `queryAll(conn, sql, mapper, params...)` share a name but take different parameters. Java picks one when compiling.

### 4.4 Abstraction: show *what*, hide *how*

**What it is:** callers work against an abstract type (an interface or abstract class) and don't care about the details.

**Abstract classes** (can't be created with `new`; can hold code and fields):
- `BaseRepository`: shared code for repositories.
- `ApiException`: declares `public abstract int status();`. Every subclass *must* implement it.

**Interfaces** (a contract: "you must have these methods"):
- `model/Validatable`: `validate()` plus **default methods** `require()`, `requirePhone()`, `requireId()` that every implementer gets for free.
- `web/Controller`: `register(Router)`.
- `web/Endpoint` and `db/SqlWork<T>`: **functional interfaces** (one method each), so lambdas can stand in for them.
- `ApiServer implements HttpHandler`: Java's own interface. We plug our object into the JDK's server.

**Abstract class vs interface (asked often):**

| | Abstract class | Interface |
| --- | --- | --- |
| How many can a class use? | extends **one** | implements **many** |
| Fields? | yes (any kind) | only `static final` constants |
| Constructor? | yes | no |
| Use when | sharing code between related classes (`BaseRepository`) | a capability unrelated classes share (`Validatable`) |

---

## 5. Other Java concepts in the code

| Concept | Where | One line to say |
| --- | --- | --- |
| **Class and object** | `new StudentService(...)` in `Main` | A class is the blueprint; `new` makes an object (an instance) |
| **Constructor** | every service; `Database(AppConfig)` | Runs when the object is made and sets its fields |
| **`this`** | `this.db = db;` in every constructor | The current object; tells the field apart from the parameter |
| **`super`** | `ApiException` subclasses: `super(message)` | Calls the parent's constructor |
| **`static`** | `AppConfig.today()`, `Json.MAPPER` | Belongs to the class, not to any object |
| **`final`** | all service fields; `final class Json` | A final variable can't be reassigned; a final class can't be extended |
| **Records** | `Student`, `Booking`, `AppConfig`, `Requests.*` | Immutable data classes; Java writes the constructor, getters, `equals`, `hashCode`, `toString` |
| **Compact constructor** | `AppConfig { ... }` | Validates before the record exists (fail fast) |
| **Enum** | `MealStatus` (with a field and constructor), `HttpMethod` | A fixed set of named constants, type-safe |
| **Generics** | `SqlWork<T>`, `<T> T inTransaction(...)`, `RowMapper<T>`, `Optional<T>`, `List<Map<String,Object>>` | One piece of code that works for many types, checked when compiling |
| **Bounded generics** | `<T extends Validatable> T body(Class<T>)` | "Any type, as long as it is a Validatable" |
| **Lambdas** | `rs -> new Student(...)`, every route | A short function passed as an object |
| **Method references** | `menu::menu`, `Booking::label`, `ApiException.Unauthorized::new` | Shorthand for a lambda that just calls a method or constructor |
| **Exception handling** | `ApiServer.answer()`, `try/catch` in `StaffService.serve()` | Catch specific exceptions and turn each into the right HTTP answer |
| **Custom exceptions** | `ApiException` and its subclasses | Our own exception types carrying an HTTP status |
| **Checked vs unchecked** | `SQLException` (checked, must be declared), `ApiException` (unchecked, extends `RuntimeException`) | Checked ones must be caught or declared with `throws` |
| **try-with-resources** | `Database.inTransaction()`, `BaseRepository` | Auto-closes connections and statements, even after an error |
| **Nested / inner types** | `Requests.Phone`, `ApiException.BadRequest`, `AuthService.PendingCode` | Related small types grouped inside one class |
| **Composition ("has-a")** | `AuthService` has a `TokenService`, a `RateLimiter` and a `StudentRepository`; `Booking` has a `MealStatus` | Build objects out of other objects (preferred over inheritance) |
| **Immutability** | records; `List.copyOf()` in `AppConfig` | Objects that can't change are safe to share between threads |
| **Collections** | `HashMap` (Router), `ArrayDeque` (RateLimiter), `List`, `LinkedHashMap` (keeps order) | Java's built-in data structures |
| **Optional** | `findByPhone()` returns `Optional<Student>` | Says "maybe no result" without returning `null` |
| **Pattern matching** | `if (value instanceof BigDecimal d)` | Type check and cast in one step |
| **Switch expression** | `BaseRepository.jsonValue()` | `switch` that returns a value with `->` |
| **Threads / `synchronized`** | 16-thread pool in `ApiServer`; `RateLimiter`; `synchronized (codes)` in `AuthService` | Many requests at once; only one thread changes shared data at a time |
| **Packages** | `com.muj.mess.config`, `.db`, `.model`, `.repository`, `.service`, `.web` | Group related classes, control visibility |
| **Private constructor** | `Json`, `Requests` | Stops anyone creating an object of a utility class |
| **Interface default methods** | `Validatable.require()` | An interface method with a body |
| **Unit testing (JUnit 5)** | `backend/src/test/java` | `TokenServiceTest` proves a forged token is refused |

## 6. Design patterns (name them, they earn marks)

| Pattern | Where | Why |
| --- | --- | --- |
| **Layered architecture** | controller → service → repository | Separation of concerns |
| **Repository Pattern** | `repository/` | All SQL in one place; services never write SQL |
| **Dependency Injection** (by hand) | `Main.java` passes objects into constructors | Loose coupling; easy to test or swap parts |
| **Template Method** (light) | `BaseRepository` gives the fixed steps (prepare → run → map); each subclass gives the SQL and the mapper | Reuse the steps, vary the details |
| **Strategy** (via lambdas) | `RowMapper<T>`, `SqlWork<T>`, `Endpoint` | Pass behaviour in as an object |
| **Front Controller** | `ApiServer` gets every request and dispatches it | One place for CORS, errors and JSON |
| **Static Factory Method** | `AppConfig.load()`, `MealStatus.fromDb()` | A named way to build objects |
| **Wrapper / Adapter** | `ApiRequest` wraps `HttpExchange` | A simpler interface over a library class |

---

## 7. Questions the examiner may ask

**Q: Where is encapsulation in your project?**
`Database` keeps the URL and password `private final`. Other classes can only call `inTransaction()`. `RateLimiter`'s map is private and changed only through `tryAcquire()`.

**Q: Show me inheritance.**
`StudentRepository extends BaseRepository` inherits `queryOne`, `queryAll` and `execute`. The second hierarchy is `ApiException`, with seven subclasses like `BadRequest` and `Conflict`.

**Q: Show me runtime polymorphism.**
`ApiServer.answer()` catches any `ApiException` and calls `e.status()`. Each subclass overrides it, so `NotFound` gives 404 and `Conflict` gives 409, decided at runtime. Also `List<Controller>` in `Main`.

**Q: Overloading vs overriding?**
Overloading means same name, different parameters, chosen at compile time (`queryAll` with or without a mapper). Overriding means a subclass replaces a parent's method with the same signature, chosen at runtime (`status()`, `validate()`, `handle()`, `toString()`).

**Q: Why is `BaseRepository` abstract and not an interface?**
It has real shared code: the JDBC helpers. An interface is a contract, and an abstract class shares implementation. Nobody should create a "base repository" on its own.

**Q: Why use records?**
Data that shouldn't change: `Student`, `Booking` and the requests. Java writes the constructor, getters, `equals`, `hashCode` and `toString`. They're immutable, so they're thread-safe.

**Q: What is a functional interface? Where?**
An interface with exactly one abstract method, so a lambda can implement it: `SqlWork<T>`, `Endpoint`, `RowMapper<T>`. Every route is a lambda: `r.get("/menu", req -> Map.of("slots", students.menu()))`.

**Q: What are generics for? Example?**
Type safety without rewriting code. `<T> T inTransaction(SqlWork<T> work)` returns a `Boolean` for one call and a `List` for another, checked by the compiler.

**Q: How do you stop SQL injection?**
Every query is a `PreparedStatement` with `?` placeholders (`BaseRepository.prepare()`). User input is never glued into SQL text.

**Q: How do you handle errors?**
Our own exception hierarchy. Services throw `ApiException` subclasses. `ApiServer` catches them in one place and sends `{"detail": "..."}` with the right status code. MySQL trigger errors (code 1644) become 409. Anything unexpected is logged and returns 500.

**Q: What is a transaction? Where?**
A group of SQL steps that all succeed or all fail. `Database.inTransaction()` turns auto-commit off, runs the work, commits on success, and rolls back on any exception.

**Q: How does login work?**
`/auth/check` makes a random 6-digit code with `SecureRandom` and keeps only its HMAC hash in memory for 5 minutes, with 5 tries. `/auth/demo-verify` checks it and returns a token: `base64(json{sid,exp}).HMAC-SHA256 signature`. Every student request sends `Authorization: Bearer <token>`. `TokenService` re-computes the signature and compares in constant time, so a changed token is refused.

**Q: How do staff log in?**
`X-Staff-Pin` header, checked by `AuthService.requireStaff()`.

**Q: What is dependency injection here?**
Objects don't create their own helpers. `Main` creates them and passes them through constructors: `new AuthService(db, studentRepo, tokens, pin)`. This is loose coupling, and you could pass a fake repository in a test.

**Q: Composition vs inheritance?**
Inheritance is "is-a" (`StudentRepository` is a `BaseRepository`). Composition is "has-a" (`AuthService` has a `TokenService`). We use composition for services because it's more flexible.

**Q: How does the server handle many users at once?**
`ApiServer` runs on a pool of 16 threads. Shared in-memory data (`RateLimiter`, pending codes) is protected with `synchronized`. Each request gets its own database connection.

**Q: Where's the business logic: Java or MySQL?**
Both, on purpose. Java checks input and simple rules (date within 7 days, pause at most 60 days). MySQL enforces rules that must hold however data arrives: triggers block booking a paused day, UNIQUE keys block serving twice, and `sp_close_meal` picks the NGO.

**Q: What does `static` mean? Example?**
It belongs to the class, not to an object. `AppConfig.today()` is called without creating an AppConfig. `Json.MAPPER` is one shared converter.

**Q: What does `final` mean here?**
Service fields are `final`, set once in the constructor and never changed. `Json` is a `final class`, so it can't be extended.

**Q: Why an enum for `MealStatus`?**
Only `BOOKED` and `SKIPPED` are possible, so a typo can't compile. It carries its database word (`dbValue`) and converts back with `fromDb()`.

**Q: What is `Optional`?**
A box that may be empty. `findByPhone()` returns `Optional<Student>`, so the caller must handle "no such student" (`orElseThrow(...)`). No `NullPointerException` surprises.

**Q: What libraries do you use?**
Only three: the **MySQL JDBC driver** (talk to MySQL), **Jackson** (JSON ↔ Java objects) and **JUnit 5** (tests). The HTTP server is the JDK's built-in `com.sun.net.httpserver`. **Maven** builds it (`pom.xml`), and `mvnw` downloads Maven by itself.

**Q: How does the frontend talk to the backend?**
`docs/shared.js` has `apiFetch()`, which calls `fetch()` with JSON. The Java server also serves those HTML files (`ApiServer.serveFile()`), so one `start.bat` runs everything.

**Q: Any security beyond SQL injection?**
Staff PIN and tokens are compared in constant time. Login codes are rate-limited per IP and stored hashed. Phone numbers are masked on the public dashboard. Request bodies are capped at 64 KB. Static files can't escape `docs/` (no `../`). Secrets live in `backend/.env`, which isn't in git.

**Q: Show me a test.**
`backend/src/test/java/.../TokenServiceTest.java` checks that a token gives back the same student, and that a token with a swapped body, or signed with another secret, is refused. Run `build.bat`.

---

## 8. Demo script (5 minutes)

1. `start.bat` → show the console line `MUJ Mess (Java) is running`.
2. **Student site**: log in with any number → book lunch at BluDove → **"Pause"** tomorrow → try booking tomorrow → error from the MySQL trigger. Say: *"The trigger raised error 1644, the JDBC driver threw an SQLException, and ApiServer turned it into a 409. That's our exception handling."*
3. **Staff page**: enter the PIN → serve the same number → serve again → "Already served this meal today" (UNIQUE key → `SQLIntegrityConstraintViolationException` → `ApiException.Conflict`).
4. **Close meal** → donations appear (stored procedure `sp_close_meal`).
5. **Dashboard** → live feed, profit per mess.
6. Open the code in the order of section 3: `Main` → `StudentController` → `StudentService.book` → `BookingRepository.upsert` → `BaseRepository` → `ApiException`.
7. Run `grep -rn "OOP:" backend/src` (or `findstr`) to show every concept is commented.

## 9. Files to know by heart

`Main.java`, `BaseRepository.java`, `ApiException.java`, `Validatable.java` + `Requests.java`, `StudentService.java`, `ApiServer.java`. If you understand those six, you understand the system.
