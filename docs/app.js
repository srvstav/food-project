// Student flow: login, book meals, pause/resume, live counters. motion.js only animates.
const $ = id => document.getElementById(id);

// Shown when the server is unreachable, so the page still reads well. Mirrors db/seed.sql.
const FALLBACK_MENU = { slots: [
  { slot_id: 1, name: "Breakfast", starts_at: "07:30", ends_at: "09:30", messes: [
    { mess_id: 1, name: "BluDove", dishes: ["Aloo Paratha", "Curd", "Masala Chai", "Banana"] },
    { mess_id: 2, name: "BluSpring", dishes: ["Poha", "Boiled Eggs", "Bread Butter Jam", "Cold Coffee"] } ] },
  { slot_id: 2, name: "Lunch", starts_at: "12:30", ends_at: "14:30", messes: [
    { mess_id: 1, name: "BluDove", dishes: ["Rajma", "Jeera Rice", "Tawa Roti", "Boondi Raita", "Salad"] },
    { mess_id: 2, name: "BluSpring", dishes: ["Chole", "Bhature", "Veg Pulao", "Lassi"] } ] },
  { slot_id: 3, name: "Hi-Tea", starts_at: "17:00", ends_at: "18:00", messes: [
    { mess_id: 1, name: "BluDove", dishes: ["Samosa", "Green Chutney", "Masala Chai"] },
    { mess_id: 2, name: "BluSpring", dishes: ["Veg Sandwich", "Bhel Puri", "Lemon Tea"] } ] },
  { slot_id: 4, name: "Dinner", starts_at: "19:30", ends_at: "21:30", messes: [
    { mess_id: 1, name: "BluDove", dishes: ["Paneer Butter Masala", "Dal Tadka", "Butter Naan", "Steamed Rice", "Gulab Jamun"] },
    { mess_id: 2, name: "BluSpring", dishes: ["Dal Baati Churma", "Gatte ki Sabzi", "Chapati", "Kheer"] } ] },
] };

const api = (path, opts = {}) => {
  const token = store.get("mess_token");
  return apiFetch(path, {
    ...opts,
    headers: token ? { Authorization: `Bearer ${token}` } : {},
    onUnauthorized: token ? logout : undefined,
  });
};

let menuPromise = null;
const getMenu = () => (menuPromise ??= api("/menu").catch(() => { menuPromise = null; return FALLBACK_MENU; }));
window.Mess = { getMenu, FALLBACK_MENU };

/* ---------- login ---------- */

let phone = "";

function show(step) {
  for (const id of ["step-phone", "step-otp", "step-book"]) $(id).hidden = id !== step;
}

async function withBusy(btn, fn) {
  btn.disabled = true;
  try { await fn(); } catch (e) { toast(e.message); } finally { btn.disabled = false; }
}

$("phone").addEventListener("input", e => { e.target.value = e.target.value.replace(/\D/g, "").slice(0, 10); });
$("otp").addEventListener("input", e => { e.target.value = e.target.value.replace(/\D/g, "").slice(0, 6); });

$("phone-form").addEventListener("submit", e => {
  e.preventDefault();
  const value = $("phone").value.trim();
  if (!/^[6-9]\d{9}$/.test(value)) return toast("Enter a 10-digit Indian mobile number");
  withBusy(e.target.querySelector("button[type=submit]"), async () => {
    const res = await api("/auth/request-otp", { method: "POST", body: { phone: value } });
    phone = value;
    $("otp-phone").textContent = phone;
    $("dev-otp").hidden = !res.dev_otp;
    $("dev-otp").textContent = res.dev_otp ? `Demo mode - no SMS yet. Your OTP is ${res.dev_otp}` : "";
    $("otp").value = "";
    show("step-otp");
    $("otp").focus();
  });
});

$("otp-form").addEventListener("submit", e => {
  e.preventDefault();
  const otp = $("otp").value.trim();
  if (!/^\d{6}$/.test(otp)) return toast("The OTP is 6 digits");
  withBusy(e.target.querySelector("button[type=submit]"), async () => {
    const res = await api("/auth/verify-otp", { method: "POST", body: { phone, otp } });
    store.set("mess_token", res.token);
    store.set("mess_phone", res.phone);
    await openBooking();
    toast("You're in. Pick your meals.");
  });
});

$("back").addEventListener("click", () => show("step-phone"));
$("logout").addEventListener("click", logout);

function logout() {
  store.del("mess_token");
  store.del("mess_phone");
  show("step-phone");
}

/* ---------- booking ---------- */

let selectedDate = null;

function renderDays() {
  const root = $("days");
  root.replaceChildren();
  for (let i = 0; i <= 7; i++) {
    const iso = istDay(i);
    const d = new Date(iso + "T00:00");
    const b = document.createElement("button");
    b.className = "day";
    b.setAttribute("role", "tab");
    b.setAttribute("aria-selected", String(iso === selectedDate));
    const top = document.createElement("span");
    top.textContent = i === 0 ? "Today" : i === 1 ? "Tmrw" : d.toLocaleDateString("en-IN", { weekday: "short" });
    const small = document.createElement("small");
    small.textContent = d.toLocaleDateString("en-IN", { day: "numeric", month: "short" });
    b.append(top, small);
    b.addEventListener("click", () => {
      selectedDate = iso;
      renderDays();
      renderSlots().catch(err => toast(err.message));
    });
    root.append(b);
  }
}

async function openBooking() {
  selectedDate ??= istDay(0);
  $("me-phone").textContent = "+91 " + (store.get("mess_phone") || "");
  $("pause-from").min = $("pause-to").min = istDay(0);
  $("pause-from").value ||= istDay(1);
  $("pause-to").value ||= istDay(3);
  show("step-book");
  renderDays();
  await Promise.all([renderSlots(), renderPauses()]);
}

async function renderSlots() {
  const [menu, mine] = await Promise.all([
    getMenu(),
    api(`/bookings/me?meal_date=${encodeURIComponent(selectedDate)}`),
  ]);
  const chosen = Object.fromEntries(mine.bookings.map(b => [b.slot_id, b]));
  $("paused-banner").hidden = !mine.paused;
  const root = $("slots");
  root.replaceChildren();

  for (const slot of menu.slots) {
    const current = chosen[slot.slot_id];
    const el = document.createElement("div");
    el.className = "slot" + (mine.paused ? " is-paused" : "");

    const head = document.createElement("div");
    head.className = "slot-head";
    const h3 = document.createElement("h3");
    h3.textContent = slot.name;
    const time = document.createElement("span");
    time.className = "time";
    time.textContent = `${slot.starts_at}–${slot.ends_at}`;
    head.append(h3, time);

    const choices = document.createElement("div");
    choices.className = "choices";
    for (const mess of slot.messes) {
      const b = document.createElement("button");
      b.className = "choice";
      b.dataset.mess = mess.mess_id;
      b.disabled = mine.paused;
      b.setAttribute("aria-pressed", String(current?.mess_id === mess.mess_id));
      const mini = document.createElement("span");
      mini.className = "mini";
      mini.innerHTML = window.plateSVG(mess.dishes); // our own SVG; dish names are escaped inside
      const text = document.createElement("span");
      const name = document.createElement("span");
      name.className = "name";
      name.textContent = mess.name;
      const dishes = document.createElement("span");
      dishes.className = "dishes";
      dishes.textContent = mess.dishes.join(" · ");
      text.append(name, document.createElement("br"), dishes);
      b.append(mini, text);
      b.addEventListener("click", () => book(slot, mess.mess_id));
      choices.append(b);
    }

    const skip = document.createElement("button");
    skip.className = "skip";
    skip.disabled = mine.paused;
    const status = current?.status;
    skip.setAttribute("aria-pressed", String(status === "skipped" || status === "paused"));
    skip.textContent = status === "paused" ? "Paused - you're away"
      : status === "skipped" ? "Skipping - not counted" : "Skip this meal";
    skip.addEventListener("click", () => book(slot, null));

    el.append(head, choices, skip);
    root.append(el);
  }
}

async function book(slot, messId) {
  try {
    await api("/bookings", { method: "POST", body: { meal_date: selectedDate, slot_id: slot.slot_id, mess_id: messId } });
    const mess = slot.messes.find(m => m.mess_id === messId);
    toast(mess ? `${slot.name} → ${mess.name}. Saved to MySQL.` : `${slot.name} skipped. You won't be counted.`);
    await renderSlots();
    refreshLive();
  } catch (e) {
    toast(e.message);
  }
}

/* ---------- pause / resume ---------- */

const fmt = iso => new Date(iso + "T00:00").toLocaleDateString("en-IN", { day: "numeric", month: "short" });

async function renderPauses() {
  const { pauses } = await api("/pause/me");
  const list = $("pause-list");
  list.replaceChildren();
  for (const p of pauses) {
    const li = document.createElement("li");
    li.textContent = `Away ${fmt(p.from_date)} → ${fmt(p.to_date)}`;
    list.append(li);
  }
  $("resume").hidden = pauses.length === 0;
}

$("pause-form").addEventListener("submit", e => {
  e.preventDefault();
  const from_date = $("pause-from").value, to_date = $("pause-to").value;
  if (!from_date || !to_date) return toast("Pick both dates");
  withBusy(e.target.querySelector("button[type=submit]"), async () => {
    await api("/pause", { method: "POST", body: { from_date, to_date } });
    toast(`Paused ${fmt(from_date)} → ${fmt(to_date)}. Those meals won't be cooked for you.`);
    await Promise.all([renderPauses(), renderSlots()]);
    refreshLive();
  });
});

$("resume").addEventListener("click", e => withBusy(e.currentTarget, async () => {
  await api("/resume", { method: "POST" });
  toast("Welcome back! Book your meals again.");
  await Promise.all([renderPauses(), renderSlots()]);
}));

/* ---------- live forecast from v_daily_forecast ---------- */

const lastCounts = {};

async function refreshLive() {
  try {
    const [menu, { forecast }] = await Promise.all([getMenu(), apiFetch("/stats/today")]);
    const by = Object.fromEntries(forecast.map(f => [`${f.meal}|${f.mess}`, f]));
    const total = forecast.reduce((s, f) => s + f.booked, 0);
    $("live-note").textContent = total
      ? `${total} plates booked for today. Refreshes every 5 seconds.`
      : "No bookings for today yet. Be the first. Refreshes every 5 seconds.";

    const grid = $("live-grid");
    if (!grid.children.length) {
      for (const slot of menu.slots) {
        const cell = document.createElement("div");
        cell.className = "live-cell";
        const h3 = document.createElement("h3");
        h3.textContent = slot.name;
        cell.append(h3);
        for (const mess of slot.messes) {
          const row = document.createElement("div");
          row.className = "live-mess";
          row.dataset.mess = mess.mess_id;
          row.dataset.key = `${slot.name}|${mess.name}`;
          row.innerHTML = `<span class="name"></span><span><span class="n">0</span> <span class="cook"></span></span>`;
          row.querySelector(".name").textContent = mess.name;
          cell.append(row);
        }
        grid.append(cell);
      }
    }
    for (const row of grid.querySelectorAll(".live-mess")) {
      const f = by[row.dataset.key];
      const n = f ? f.booked : 0;
      const el = row.querySelector(".n");
      if (lastCounts[row.dataset.key] !== undefined && lastCounts[row.dataset.key] !== n) {
        el.classList.remove("bump"); void el.offsetWidth; el.classList.add("bump");
      }
      lastCounts[row.dataset.key] = n;
      el.textContent = n;
      row.querySelector(".cook").textContent = `cook ${f ? f.cook_for : 0}`;
    }
  } catch {
    $("live-note").textContent = "Mess server offline right now. If you're running it locally, start it with start.bat.";
  }
}

refreshLive();
setInterval(refreshLive, 5000);

// Resume a saved session.
if (store.get("mess_token")) openBooking().catch(() => show("step-phone"));
