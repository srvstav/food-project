// Scroll animation (GSAP + ScrollTrigger). The page still works if GSAP fails to load or motion is reduced.
(async () => {
  const reduced = matchMedia("(prefers-reduced-motion: reduce)").matches;
  const hasGsap = typeof gsap !== "undefined" && typeof ScrollTrigger !== "undefined";
  const $ = id => document.getElementById(id);

  // Don't let a slow or dead server hold the page: fall back to the built-in menu after 2.5 s.
  const menu = await Promise.race([
    window.Mess.getMenu(),
    new Promise(r => setTimeout(() => r(window.Mess.FALLBACK_MENU), 2500)),
  ]);

  const MEAL_THEME = {
    Breakfast: { bg: "#FFC83A", dark: false, line: "sunrise, served" },
    Lunch:     { bg: "#FF4A1C", dark: true,  line: "the big one" },
    "Hi-Tea":  { bg: "#F8B7CB", dark: false, line: "chai o'clock" },
    Dinner:    { bg: "#1E2BD6", dark: true,  line: "lights low, plates full" },
  };

  /* ---------- build DOM from the menu ---------- */

  const dinner = menu.slots.find(s => s.name === "Dinner") || menu.slots[0];
  $("hero-plate").innerHTML = window.plateSVG(dinner.messes.flatMap(m => m.dishes).slice(0, 7), { seed: "hero" });

  const allDishes = [...new Set(menu.slots.flatMap(s => s.messes.flatMap(m => m.dishes)))];
  const marquee = $("marquee");
  for (const d of [...allDishes, ...allDishes]) {
    const s = document.createElement("span");
    s.textContent = d;
    marquee.append(s);
  }

  const track = $("meals-track");
  for (const slot of menu.slots) {
    const theme = MEAL_THEME[slot.name] || { bg: "#FFC83A", dark: false, line: "" };
    const panel = document.createElement("article");
    panel.className = "meal" + (theme.dark ? " dark" : "");
    panel.dataset.bg = theme.bg;

    const head = document.createElement("div");
    head.className = "meal-head";
    const h = document.createElement("h2");
    h.className = "meal-name";
    h.textContent = slot.name;
    const t = document.createElement("span");
    t.className = "meal-time";
    t.textContent = `${slot.starts_at}–${slot.ends_at} · ${theme.line}`;
    head.append(h, t);

    const body = document.createElement("div");
    body.className = "meal-body";
    for (const mess of slot.messes) {
      const col = document.createElement("div");
      col.className = "mess-col";
      col.dataset.mess = mess.mess_id;
      const plate = document.createElement("div");
      plate.className = "plate";
      plate.innerHTML = window.plateSVG(mess.dishes, { rim: theme.dark ? "#FFF3E0" : "#FFFFFF" });
      const info = document.createElement("div");
      const tag = document.createElement("span");
      tag.className = "mess-tag";
      tag.textContent = mess.name;
      const ul = document.createElement("ul");
      ul.className = "dish-list";
      for (const d of mess.dishes) {
        const li = document.createElement("li");
        li.textContent = d;
        ul.append(li);
      }
      info.append(tag, ul);
      col.append(plate, info);
      body.append(col);
    }
    panel.append(head, body);
    track.append(panel);
  }
  $("meals").style.backgroundColor = track.firstElementChild?.dataset.bg || "";

  // Split statement into words, hero lines into characters.
  const words = document.querySelector(".reveal-words");
  words.innerHTML = words.innerHTML.replace(/(<em>.*?<\/em>|[^\s<]+)/g, '<span class="w">$1</span>');
  for (const h of document.querySelectorAll(".hero .split")) {
    // Wrap each word so lines only break between words, never inside one.
    h.innerHTML = h.textContent.trim().split(/\s+/)
      .map(word => `<span class="word">${[...word].map(c => `<span class="ch">${c}</span>`).join("")}</span>`)
      .join(" ");
  }

  if (reduced || !hasGsap) {
    document.documentElement.classList.add("no-motion");
    document.querySelectorAll(".reveal-words .w").forEach(w => (w.style.opacity = 1));
    document.querySelectorAll(".how-num").forEach(n => (n.textContent = (n.dataset.prefix || "") + n.dataset.count + (n.dataset.suffix || "")));
    // Colour each stacked meal section itself when there is no pinned scroll.
    document.querySelectorAll(".meal").forEach(p => (p.style.background = p.dataset.bg));
    return;
  }

  gsap.registerPlugin(ScrollTrigger);

  /* ---------- hero ---------- */
  gsap.from(".hero .ch", { yPercent: 110, rotate: 8, duration: 0.9, ease: "expo.out", stagger: 0.025 });
  gsap.from([".kicker", ".lede", ".cta"], { y: 24, opacity: 0, duration: 0.8, delay: 0.5, stagger: 0.1, ease: "power3.out" });
  gsap.from("#hero-plate", { scale: 0.6, rotate: -120, opacity: 0, duration: 1.4, ease: "expo.out", delay: 0.2 });
  gsap.from(".sticker", { scale: 0, duration: 0.6, ease: "back.out(2)", delay: 1.1, stagger: 0.15 });
  gsap.to("#hero-plate", { rotate: 200, ease: "none", scrollTrigger: { trigger: ".hero", start: "top top", end: "bottom top", scrub: 1 } });
  gsap.to(".hero-copy", { yPercent: -18, opacity: 0.2, ease: "none", scrollTrigger: { trigger: ".hero", start: "top top", end: "bottom top", scrub: true } });

  /* ---------- marquee: endless, speeds up while scrolling ---------- */
  const loop = gsap.to(marquee, { xPercent: -50, duration: 40, ease: "none", repeat: -1 });
  ScrollTrigger.create({
    onUpdate: self => {
      const v = Math.min(Math.abs(self.getVelocity()) / 400, 6);
      gsap.to(loop, { timeScale: 1 + v, duration: 0.2, overwrite: true });
      gsap.to(loop, { timeScale: 1, duration: 1, delay: 0.25 });
    },
  });

  /* ---------- statement: words light up as you read ---------- */
  gsap.to(".reveal-words .w", {
    opacity: 1, stagger: 0.08, ease: "none",
    scrollTrigger: { trigger: ".statement", start: "top 75%", end: "bottom 60%", scrub: true },
  });

  /* ---------- meals: pin and scroll sideways ---------- */
  const panels = gsap.utils.toArray(".meal");
  const distance = () => track.scrollWidth - innerWidth;
  const horizontal = gsap.to(track, {
    x: () => -distance(), ease: "none",
    scrollTrigger: {
      trigger: "#meals", start: "top top", end: () => "+=" + distance(), pin: true, scrub: 1, invalidateOnRefresh: true,
      onUpdate: self => gsap.set("#meals-bar", { scaleX: self.progress }),
    },
  });
  panels.forEach(panel => {
    ScrollTrigger.create({
      trigger: panel, containerAnimation: horizontal, start: "left 55%", end: "right 55%",
      onToggle: self => self.isActive && gsap.to("#meals", { backgroundColor: panel.dataset.bg, duration: 0.5 }),
    });
    gsap.from(panel.querySelector(".meal-name"), {
      yPercent: 60, opacity: 0, ease: "power3.out",
      scrollTrigger: { trigger: panel, containerAnimation: horizontal, start: "left 85%", end: "left 35%", scrub: true },
    });
    panel.querySelectorAll(".plate").forEach((plate, i) => {
      gsap.fromTo(plate, { rotate: i ? 90 : -90, scale: 0.7 }, {
        rotate: i ? -90 : 90, scale: 1, ease: "none",
        scrollTrigger: { trigger: panel, containerAnimation: horizontal, start: "left right", end: "right left", scrub: true },
      });
    });
    gsap.from(panel.querySelectorAll(".dish-list li"), {
      x: 60, opacity: 0, stagger: 0.06, ease: "power2.out",
      scrollTrigger: { trigger: panel, containerAnimation: horizontal, start: "left 70%", end: "left 20%", scrub: true },
    });
  });

  /* ---------- numbers count up ---------- */
  document.querySelectorAll(".how-num").forEach(n => {
    const obj = { v: 0 };
    const target = +n.dataset.count;
    const paint = () => (n.textContent = (n.dataset.prefix || "") + Math.round(obj.v) + (n.dataset.suffix || ""));
    paint();
    gsap.to(obj, { v: target, duration: 1.4, ease: "power3.out", onUpdate: paint, scrollTrigger: { trigger: n, start: "top 85%" } });
    gsap.from(n.nextElementSibling, { y: 30, opacity: 0, duration: 0.8, scrollTrigger: { trigger: n, start: "top 85%" } });
  });

  /* ---------- live + book ---------- */
  gsap.from(".live-head h2", { yPercent: 40, opacity: 0, duration: 1, ease: "expo.out", scrollTrigger: { trigger: ".live", start: "top 75%" } });
  gsap.from(".book-panel", { y: 80, rotate: 3, opacity: 0, duration: 1, ease: "expo.out", scrollTrigger: { trigger: ".book", start: "top 70%" } });
  gsap.from(".foot-big", { yPercent: 30, opacity: 0, duration: 1, ease: "expo.out", scrollTrigger: { trigger: ".foot", start: "top 80%" } });

  // Smooth in-page anchor jumps that account for the pinned section.
  document.querySelectorAll('a[href^="#"]').forEach(a => a.addEventListener("click", e => {
    const target = document.querySelector(a.getAttribute("href"));
    if (!target) return;
    e.preventDefault();
    window.scrollTo({ top: target.getBoundingClientRect().top + scrollY, behavior: "smooth" });
  }));

  addEventListener("load", () => ScrollTrigger.refresh());
})();
