/* SafeDay shared behaviour for /ui.css: icons, tooltips, the side drawer and sortable tables.
   Load with <script src="/ui.js" defer></script> before the page script. Exposes window.SafeUI. */
(() => {
  const SPRITE = "/vendor/icons.svg";
  const TIP_DELAY_MS = 300;
  const TIP_GAP_PX = 8;
  const TIP_INSTANT_WINDOW_MS = 400;

  /* <svg> markup for a Lucide icon in the sprite, for HTML built in strings. */
  function icon(name, className = "") {
    return `<svg class="i ${className}" aria-hidden="true" focusable="false"><use href="${SPRITE}#${name}"/></svg>`;
  }

  /* A help button that shows `text` as a tooltip and to screen readers. */
  function help(text) {
    const safe = String(text).replace(/[&<>"']/g, (c) => `&#${c.charCodeAt(0)};`);
    return `<button type="button" class="help" data-tip="${safe}" aria-label="${safe}">${icon("info")}</button>`;
  }

  /* ---------- tooltips: one floating label for every [data-tip] ---------- */
  let tip = null;
  let showTimer = 0;
  let lastHiddenAt = 0;

  function tipElement() {
    if (!tip) {
      tip = document.createElement("div");
      tip.className = "tooltip";
      tip.setAttribute("role", "tooltip");
      document.body.append(tip);
    }
    return tip;
  }

  function placeTip(target) {
    const box = target.getBoundingClientRect();
    const el = tipElement();
    const width = el.offsetWidth;
    const height = el.offsetHeight;
    const left = Math.min(Math.max(TIP_GAP_PX, box.left + box.width / 2 - width / 2), innerWidth - width - TIP_GAP_PX);
    const below = box.bottom + TIP_GAP_PX + height < innerHeight;
    el.style.left = `${left}px`;
    el.style.top = `${below ? box.bottom + TIP_GAP_PX : box.top - TIP_GAP_PX - height}px`;
    el.style.setProperty("--tip-origin", below ? "top center" : "bottom center");
  }

  function showTip(target) {
    clearTimeout(showTimer);
    const instant = performance.now() - lastHiddenAt < TIP_INSTANT_WINDOW_MS || tip?.classList.contains("on");
    const reveal = () => {
      const el = tipElement();
      el.textContent = target.dataset.tip;
      el.classList.toggle("instant", instant);
      placeTip(target);
      el.classList.add("on");
    };
    if (instant) reveal();
    else showTimer = setTimeout(reveal, TIP_DELAY_MS);
  }

  function hideTip() {
    clearTimeout(showTimer);
    if (tip?.classList.contains("on")) {
      tip.classList.remove("on");
      lastHiddenAt = performance.now();
    }
  }

  const tipTarget = (event) => event.target instanceof Element ? event.target.closest("[data-tip]") : null;
  document.addEventListener("pointerover", (event) => {
    const target = tipTarget(event);
    if (target && event.pointerType !== "touch") showTip(target);
  });
  document.addEventListener("pointerout", (event) => {
    if (tipTarget(event) && !event.relatedTarget?.closest?.("[data-tip]")) hideTip();
  });
  document.addEventListener("focusin", (event) => {
    const target = tipTarget(event);
    if (target && target.matches(":focus-visible")) showTip(target);
  });
  document.addEventListener("focusout", hideTip);
  document.addEventListener("click", (event) => {
    const target = tipTarget(event);
    if (target?.classList.contains("help")) {
      if (tip?.classList.contains("on")) hideTip();
      else { lastHiddenAt = performance.now(); showTip(target); }
    } else hideTip();
  });
  document.addEventListener("keydown", (event) => { if (event.key === "Escape") hideTip(); });
  addEventListener("scroll", hideTip, { passive: true, capture: true });

  /* ---------- drawer ---------- */
  /* Fill and open the shared <dialog class="drawer" id="drawer">, creating it on first use. */
  function openDrawer({ title, subtitle = "", body }) {
    let dialog = document.getElementById("drawer");
    if (!dialog) {
      dialog = document.createElement("dialog");
      dialog.id = "drawer";
      dialog.className = "drawer";
      dialog.setAttribute("aria-labelledby", "drawer-title");
      dialog.addEventListener("click", (event) => { if (event.target === dialog) dialog.close(); });
      document.body.append(dialog);
    }
    dialog.innerHTML = `
      <header class="drawer-head">
        <div><h2 id="drawer-title"></h2>${subtitle ? `<p class="fine" style="margin-top:4px">${subtitle}</p>` : ""}</div>
        <button type="button" class="icon-btn" data-close aria-label="Close">${icon("x")}</button>
      </header>
      <div class="drawer-body">${body}</div>`;
    dialog.querySelector("#drawer-title").textContent = title;
    dialog.querySelector("[data-close]").addEventListener("click", () => dialog.close());
    dialog.showModal();
    dialog.scrollTop = 0;
    return dialog;
  }

  /* ---------- sortable tables ---------- */
  /* Sort rows of `table` (one <tbody>) when a header's .sort button is pressed.
     A cell's data-value, when present, is what sorts; numbers sort as numbers. */
  function sortable(table) {
    const headers = [...table.querySelectorAll("thead th")];
    headers.forEach((th, column) => {
      const button = th.querySelector(".sort");
      if (!button) return;
      button.addEventListener("click", () => {
        const ascending = th.getAttribute("aria-sort") !== "ascending";
        headers.forEach((other) => other.removeAttribute("aria-sort"));
        th.setAttribute("aria-sort", ascending ? "ascending" : "descending");
        const body = table.tBodies[0];
        const value = (row) => {
          const cell = row.cells[column];
          const raw = cell?.dataset.value ?? cell?.textContent.trim() ?? "";
          const number = Number(raw);
          return raw !== "" && !Number.isNaN(number) ? number : raw.toLowerCase();
        };
        const rows = [...body.rows].sort((a, b) => {
          const [x, y] = [value(a), value(b)];
          const order = typeof x === "number" && typeof y === "number" ? x - y : String(x).localeCompare(String(y));
          return ascending ? order : -order;
        });
        body.append(...rows);
        table.dispatchEvent(new CustomEvent("sorted"));
      });
    });
  }

  window.SafeUI = { icon, help, openDrawer, sortable };
})();
