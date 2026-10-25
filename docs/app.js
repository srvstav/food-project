// ?api=<url> overrides the backend and is remembered, so the tunnel URL can change without a redeploy.
const API = (() => {
  const fromQuery = new URLSearchParams(location.search).get("api");
  try {
    if (fromQuery && /^https?:\/\//.test(fromQuery)) localStorage.setItem("mess_api", fromQuery.replace(/\/$/, ""));
    return localStorage.getItem("mess_api") || window.MESS_API_DEFAULT;
  } catch { return fromQuery || window.MESS_API_DEFAULT; }
})();

const $ = id => document.getElementById(id);
const store = {
  get: k => { try { return localStorage.getItem(k); } catch { return null; } },
  set: (k, v) => { try { localStorage.setItem(k, v); } catch {} },
  del: k => { try { localStorage.removeItem(k); } catch {} },
};

let menu = null;
let phone = "";

function toast(msg) {
  const t = $("toast");
  t.textContent = msg;
  t.classList.add("show");
  clearTimeout(toast.timer);
  toast.timer = setTimeout(() => t.classList.remove("show"), 2400);
}

async function api(path, { method = "GET", body } = {}) {
  const headers = { "Content-Type": "application/json" };
  const token = store.get("mess_token");
  if (token) headers.Authorization = `Bearer ${token}`;
  let res;
  try {
    res = await fetch(API + path, { method, headers, body: body ? JSON.stringify(body) : undefined });
  } catch {
    throw new Error("Can't reach the mess server");
  }
  const data = await res.json().catch(() => ({}));
  if (res.status === 401) { logout(); throw new Error("Please log in again"); }
  if (!res.ok) {
    const d = data.detail;
    throw new Error(typeof d === "string" ? d : "Check what you entered");
  }
  return data;
}

function show(step) {
  for (const id of ["step-phone", "step-otp", "step-book"]) $(id).hidden = id !== step;
  $("logout").hidden = step !== "step-book";
}

async function withBusy(form, fn) {
  const btn = form.querySelector("button[type=submit]");
  btn.disabled = true;
  try { await fn(); } catch (e) { toast(e.message); } finally { btn.disabled = false; }
}

$("phone-form").addEventListener("submit", e => {
  e.preventDefault();
  const value = $("phone").value.trim();
  if (!/^[6-9]\d{9}$/.test(value)) return toast("Enter a 10-digit mobile number");
  withBusy(e.target, async () => {
    const res = await api("/auth/request-otp", { method: "POST", body: { phone: value } });
    phone = value;
    $("otp-phone").textContent = phone;
    $("dev-otp").hidden = !res.dev_otp;
    $("dev-otp").textContent = res.dev_otp ? `Demo mode (no SMS yet): your OTP is ${res.dev_otp}` : "";
    $("otp").value = "";
    show("step-otp");
    $("otp").focus();
  });
});

$("otp-form").addEventListener("submit", e => {
  e.preventDefault();
  const otp = $("otp").value.trim();
  if (!/^\d{6}$/.test(otp)) return toast("OTP is 6 digits");
  withBusy(e.target, async () => {
    const res = await api("/auth/verify-otp", { method: "POST", body: { phone, otp } });
    store.set("mess_token", res.token);
    await openBooking();
  });
});

$("back").addEventListener("click", () => show("step-phone"));
$("logout").addEventListener("click", logout);

function logout() {
  store.del("mess_token");
  show("step-phone");
}

function isoToday(offsetDays = 0) {
  const d = new Date();
  d.setDate(d.getDate() + offsetDays);
  return new Date(d.getTime() - d.getTimezoneOffset() * 60000).toISOString().slice(0, 10);
}

async function openBooking() {
  if (!menu) menu = await api("/menu");
  const date = $("date");
  date.min = isoToday();
  date.max = isoToday(7);
  if (!date.value) date.value = isoToday();
  show("step-book");
  await renderSlots();
}

$("date").addEventListener("change", () => renderSlots().catch(e => toast(e.message)));

async function renderSlots() {
  const date = $("date").value;
  const { bookings } = await api(`/bookings/me?meal_date=${encodeURIComponent(date)}`);
  const chosen = Object.fromEntries(bookings.map(b => [b.slot_id, b]));
  const root = $("slots");
  root.replaceChildren();

  for (const slot of menu.slots) {
    const current = chosen[slot.slot_id];
    const el = document.createElement("div");
    el.className = "slot";

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
      b.setAttribute("aria-pressed", String(current?.mess_id === mess.mess_id));
      const name = document.createElement("span");
      name.className = "name";
      name.textContent = mess.name;
      const dishes = document.createElement("span");
      dishes.className = "dishes";
      dishes.textContent = mess.dishes.join(" · ");
      b.append(name, dishes);
      b.addEventListener("click", () => book(date, slot, mess.mess_id));
      choices.append(b);
    }

    const skip = document.createElement("button");
    skip.className = "skip";
    skip.setAttribute("aria-pressed", String(current?.status === "skipped"));
    skip.textContent = current?.status === "skipped" ? "Skipping this meal" : "I'll skip this meal";
    skip.addEventListener("click", () => book(date, slot, null));

    el.append(head, choices, skip);
    root.append(el);
  }
}

async function book(date, slot, messId) {
  try {
    await api("/bookings", { method: "POST", body: { meal_date: date, slot_id: slot.slot_id, mess_id: messId } });
    const mess = slot.messes.find(m => m.mess_id === messId);
    toast(mess ? `${slot.name} booked at ${mess.name}` : `${slot.name} skipped`);
    await renderSlots();
  } catch (e) {
    toast(e.message);
  }
}

// Resume a session if a token is saved.
if (store.get("mess_token")) openBooking().catch(() => show("step-phone"));
