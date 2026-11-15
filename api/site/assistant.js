/* Payung's one assistant: a chat button at the bottom of every page (/api/assistant/chat).
   Pick English, Chinese, Malay or Tamil: replies come back in that language whatever you type
   or say. The server runs the tools and returns actions the page carries out: fill the sign-up
   form, or start sign-up with details the chat worked out. The conversation lives in this tab
   only (sessionStorage).
   Voice: the mic records and the server's Whisper writes down the words in the picked language
   (/api/assistant/listen); replies are read by a neural voice in that language
   (/api/assistant/speak). Where the server has no voice, the browser's own speech is used. */
"use strict";

(() => {
  const LANGS = [
    { key: "en", label: "English", speech: "en-SG" },
    { key: "zh", label: "中文", speech: "zh-CN" },
    { key: "ms", label: "Melayu", speech: "ms-MY" },
    { key: "ta", label: "தமிழ்", speech: "ta-IN" },
  ];
  const GREETING = {
    en: "Hi! I can find cover for your business, explain your price, tell you why a day did or didn't pay, and fill forms for you. Type or tap the mic.",
    zh: "您好！我可以为您的生意找保障、解释保费、说明某天为何有或没有赔付，也能帮您填表。请打字或按麦克风说话。",
    ms: "Hai! Saya boleh cari perlindungan untuk perniagaan anda, terangkan harga, beritahu kenapa sesuatu hari dibayar atau tidak, dan isi borang untuk anda.",
    ta: "வணக்கம்! உங்கள் வணிகத்திற்கான காப்பீட்டைக் கண்டறிய, விலையை விளக்க, ஒரு நாள் ஏன் பணம் கிடைத்தது அல்லது கிடைக்கவில்லை என்று சொல்ல, படிவங்களை நிரப்ப உதவுவேன்.",
  };
  const PAGE = location.pathname.startsWith("/map") ? "map"
    : location.pathname.startsWith("/buy") ? "buy"
    : location.pathname.startsWith("/dashboard") ? "dashboard"
    : location.pathname.startsWith("/admin") ? "admin" : "site";
  const SUGGEST = {
    site: ["I sell chicken rice at Maxwell Food Centre", "Why does cover cost what it does?"],
    buy: ["My name is Tan Ah Hock, phone 9123 4567", "Which tier should I choose?"],
    dashboard: ["What is my cover?", "Why did I get paid yesterday?", "What would I have got in the last 10 years?"],
    map: ["What's the weather at Bedok today?", "What if PSI hits 250 island-wide?"],
    admin: ["What if the haze weight goes to 0.9?", "Summarise the underwriting queue"],
  };
  const STORE_KEY = "safeday-assistant", PREFILL_KEY = "safeday-prefill", VOICE_KEY = "safeday-voice";
  const store = {
    get(key, fallback) { try { return JSON.parse(sessionStorage.getItem(key)) ?? fallback; } catch { return fallback; } },
    set(key, value) { try { sessionStorage.setItem(key, JSON.stringify(value)); } catch { /* private window */ } },
  };
  const state = store.get(STORE_KEY, { messages: [], lang: "en", open: false });
  let readAloud = (() => { try { return localStorage.getItem(VOICE_KEY) === "on"; } catch { return false; } })();
  let busy = false, recognition = null, recorder = null, playing = null;
  let serverVoice = { listen: false, speak: false };
  fetch("/api/assistant/voice").then((r) => (r.ok ? r.json() : serverVoice))
    .then((v) => { serverVoice = v; }).catch(() => {});
  const MAX_RECORD_MS = 20000;

  const escapeHtml = (text) => text.replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c]);
  const render = (text) => escapeHtml(text)
    .replace(/\*\*(.+?)\*\*/g, "<b>$1</b>")
    .replace(/^\s*[-•]\s+(.+)$/gm, "<li>$1</li>")
    .replace(/(<li>.*<\/li>)/gs, "<ul>$1</ul>")
    .replace(/\n/g, "<br>");
  const speechLang = () => LANGS.find((l) => l.key === state.lang).speech;

  /* ---------- markup ---------- */
  const root = document.createElement("div");
  root.className = `sd-widget sd-${PAGE}`;
  root.innerHTML = `
    <button class="sd-launch" type="button" aria-expanded="false" aria-controls="sd-panel">
      <span class="sd-dot" aria-hidden="true"></span> Ask Payung
    </button>
    <section class="sd-panel" id="sd-panel" role="dialog" aria-label="Payung assistant" hidden>
      <header>
        <img class="sd-mark" src="/brand/payung-icon-96.png?v=1" alt="" width="22" height="22" />
        <b>Payung assistant</b>
        <select class="sd-lang" aria-label="Language">
          ${LANGS.map((l) => `<option value="${l.key}">${l.label}</option>`).join("")}
        </select>
        <button class="sd-icon sd-voice" type="button" title="Read replies aloud" aria-pressed="false">🔈</button>
        <button class="sd-icon sd-reset" type="button" title="New conversation">↺</button>
        <button class="sd-icon sd-close" type="button" title="Close">✕</button>
      </header>
      <div class="sd-log" aria-live="polite"></div>
      <div class="sd-chips"></div>
      <form class="sd-input">
        <textarea rows="1" maxlength="1500" placeholder="Type or tap the mic…" aria-label="Message"></textarea>
        <button class="sd-icon sd-mic" type="button" title="Speak">🎤</button>
        <button class="sd-send" type="submit">Send</button>
      </form>
      <p class="sd-fine">Answers use Payung's own numbers. The assistant never sets a price or decides a payout.</p>
    </section>`;
  document.body.appendChild(root);
  const $ = (sel) => root.querySelector(sel);
  const panel = $(".sd-panel"), log = $(".sd-log"), input = $("textarea"), launch = $(".sd-launch");

  /* ---------- conversation ---------- */
  function save() { store.set(STORE_KEY, state); }

  function bubble(role, text, actions = []) {
    const item = document.createElement("div");
    item.className = `sd-msg sd-${role}`;
    item.innerHTML = `<div class="sd-text">${render(text)}</div>`;
    if (role === "assistant") {
      const say = document.createElement("button");
      say.className = "sd-say"; say.type = "button"; say.title = "Read aloud"; say.textContent = "🔈";
      say.addEventListener("click", () => speak(text));
      item.appendChild(say);
    }
    for (const action of actions) item.appendChild(actionButton(action));
    log.appendChild(item);
    log.scrollTop = log.scrollHeight;
  }

  function redraw() {
    log.innerHTML = "";
    bubble("assistant", GREETING[state.lang]);
    for (const m of state.messages) bubble(m.role, m.content, m.actions || []);
    $(".sd-chips").innerHTML = state.messages.length ? "" : (SUGGEST[PAGE] || SUGGEST.site)
      .map((s) => `<button type="button" class="sd-chip">${escapeHtml(s)}</button>`).join("");
    $(".sd-chips").querySelectorAll(".sd-chip").forEach((b) => b.addEventListener("click", () => send(b.textContent)));
  }

  async function send(text) {
    text = text.trim();
    if (!text || busy) return;
    busy = true;
    input.value = "";
    state.messages.push({ role: "user", content: text });
    save(); redraw();
    const typing = document.createElement("div");
    typing.className = "sd-msg sd-assistant sd-typing";
    typing.innerHTML = "<div class='sd-text'><span></span><span></span><span></span></div>";
    log.appendChild(typing); log.scrollTop = log.scrollHeight;
    try {
      const response = await fetch("/api/assistant/chat", {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          page: PAGE,
          language: state.lang,
          messages: state.messages.slice(-12).map(({ role, content }) => ({ role, content })),
        }),
      });
      const body = await response.json();
      if (!response.ok) throw new Error(body.detail || `HTTP ${response.status}`);
      for (const action of body.actions || []) if (action.type === "fill_form") fillForm(action.fields);
      state.messages.push({ role: "assistant", content: body.reply, actions: (body.actions || []).filter((a) => a.type !== "fill_form") });
      if (readAloud) speak(body.reply);
    } catch (error) {
      state.messages.push({ role: "assistant", content: `Sorry, I couldn't answer that just now (${error.message}). Please try again.` });
    } finally {
      busy = false; save(); redraw();
    }
  }

  /* ---------- actions ---------- */
  function actionButton(action) {
    const button = document.createElement("button");
    button.type = "button"; button.className = "sd-action";
    button.textContent = action.label || "Open";
    button.addEventListener("click", () => {
      if (action.fields) store.set(PREFILL_KEY, action.fields);
      if (PAGE === "buy" && action.fields) { fillForm(action.fields); return; }
      if (action.url) location.href = action.url;
    });
    return button;
  }

  function setField(form, name, value) {
    const fields = form.querySelectorAll(`[name="${name}"]`);
    if (!fields.length) return false;
    const first = fields[0];
    if (first.type === "radio") {
      const radio = [...fields].find((f) => f.value === value);
      if (!radio) return false;
      radio.checked = true;
      radio.dispatchEvent(new Event("change", { bubbles: true }));
      radio.closest("label")?.classList.add("sd-filled");
      return true;
    }
    if (first.tagName === "SELECT" && ![...first.options].some((o) => o.value === value)) return false;
    first.value = value;
    first.dispatchEvent(new Event("input", { bubbles: true }));
    first.dispatchEvent(new Event("change", { bubbles: true }));
    first.classList.add("sd-filled");
    return true;
  }

  // Selects fill once buy.js has loaded their options, and later fields appear only after an
  // earlier choice (the business class), so retry for a few seconds.
  function fillForm(fields, attempt = 0) {
    const form = document.getElementById("buy");
    if (!form || !fields) return;
    const order = ["business_class", ...Object.keys(fields).filter((k) => k !== "business_class")];
    const left = {};
    for (const name of order) {
      if (fields[name] === undefined) continue;
      if (!setField(form, name, String(fields[name]))) left[name] = fields[name];
    }
    if (Object.keys(left).length && attempt < 12) setTimeout(() => fillForm(left, attempt + 1), 400);
  }

  /* ---------- voice ---------- */
  function stopSpeaking() {
    if (playing) { playing.pause(); playing = null; }
    if ("speechSynthesis" in window) speechSynthesis.cancel();
  }

  async function speak(text) {
    stopSpeaking();
    const clean = text.replace(/\*\*/g, "");
    if (serverVoice.speak) {
      try {
        const response = await fetch("/api/assistant/speak", {
          method: "POST", headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ text: clean.slice(0, 1500), language: state.lang }),
        });
        if (!response.ok) throw new Error(`HTTP ${response.status}`);
        playing = new Audio(URL.createObjectURL(await response.blob()));
        await playing.play();
        return;
      } catch { /* fall back to the browser's own voices */ }
    }
    browserSpeak(clean);
  }

  function browserSpeak(text) {
    if (!("speechSynthesis" in window)) return;
    const utterance = new SpeechSynthesisUtterance(text);
    utterance.lang = speechLang();
    const voice = speechSynthesis.getVoices().find((v) => v.lang.toLowerCase().startsWith(state.lang));
    if (voice) utterance.voice = voice;
    utterance.rate = 0.95;
    speechSynthesis.speak(utterance);
  }

  async function listen() {
    const mic = $(".sd-mic");
    if (recorder) { recorder.stop(); return; }
    if (serverVoice.listen && navigator.mediaDevices && window.MediaRecorder) {
      let stream;
      try { stream = await navigator.mediaDevices.getUserMedia({ audio: true }); } catch {
        bubble("assistant", "I can't hear you: allow the microphone for this site and try again.");
        return;
      }
      const chunks = [];
      recorder = new MediaRecorder(stream);
      recorder.ondataavailable = (event) => { if (event.data.size) chunks.push(event.data); };
      recorder.onstop = async () => {
        stream.getTracks().forEach((track) => track.stop());
        mic.classList.remove("sd-live");
        recorder = null;
        input.placeholder = "Writing down what you said…";
        try {
          const audio = new Blob(chunks, { type: chunks[0]?.type || "audio/webm" });
          const response = await fetch(`/api/assistant/listen?language=${state.lang}`, {
            method: "POST", headers: { "Content-Type": audio.type }, body: audio,
          });
          const body = await response.json();
          if (!response.ok) throw new Error(body.detail || `HTTP ${response.status}`);
          if (body.text) send(body.text);
          else bubble("assistant", "I didn't catch anything. Please tap the mic and speak a little closer.");
        } catch (error) {
          bubble("assistant", `I couldn't make out the recording (${error.message}). Please try again or type.`);
        } finally {
          input.placeholder = "Type or tap the mic…";
        }
      };
      recorder.start();
      mic.classList.add("sd-live");
      input.placeholder = "Listening… tap the mic again when you finish";
      setTimeout(() => recorder?.state === "recording" && recorder.stop(), MAX_RECORD_MS);
      return;
    }
    browserListen();
  }

  function browserListen() {
    const Recognition = window.SpeechRecognition || window.webkitSpeechRecognition;
    if (!Recognition) {
      bubble("assistant", "Your browser can't take speech here. Chrome, Edge and Safari can.");
      return;
    }
    if (recognition) { recognition.stop(); return; }
    recognition = new Recognition();
    recognition.lang = speechLang();
    recognition.interimResults = true;
    recognition.onresult = (event) => {
      input.value = [...event.results].map((r) => r[0].transcript).join(" ");
    };
    recognition.onend = () => {
      $(".sd-mic").classList.remove("sd-live");
      recognition = null;
      if (input.value.trim()) send(input.value);
    };
    recognition.onerror = () => $(".sd-mic").classList.remove("sd-live");
    $(".sd-mic").classList.add("sd-live");
    recognition.start();
  }

  /* ---------- wiring ---------- */
  function setOpen(open) {
    state.open = open; save();
    panel.hidden = !open;
    launch.setAttribute("aria-expanded", String(open));
    if (open) { redraw(); input.focus(); }
  }
  launch.addEventListener("click", () => setOpen(panel.hidden));
  $(".sd-close").addEventListener("click", () => setOpen(false));
  $(".sd-reset").addEventListener("click", () => { state.messages = []; save(); redraw(); });
  $(".sd-lang").value = state.lang;
  $(".sd-lang").addEventListener("change", (e) => { state.lang = e.target.value; save(); redraw(); });
  const voiceButton = $(".sd-voice");
  const paintVoice = () => {
    voiceButton.textContent = readAloud ? "🔊" : "🔈";
    voiceButton.setAttribute("aria-pressed", String(readAloud));
  };
  paintVoice();
  voiceButton.addEventListener("click", () => {
    readAloud = !readAloud;
    try { localStorage.setItem(VOICE_KEY, readAloud ? "on" : "off"); } catch { /* private window */ }
    if (!readAloud) stopSpeaking();
    paintVoice();
  });
  $(".sd-mic").addEventListener("click", listen);
  $(".sd-input").addEventListener("submit", (e) => { e.preventDefault(); send(input.value); });
  input.addEventListener("keydown", (e) => {
    if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); send(input.value); }
  });
  document.addEventListener("keydown", (e) => { if (e.key === "Escape" && !panel.hidden) setOpen(false); });

  // Details the chat worked out on another page wait here until the sign-up form is ready.
  if (PAGE === "buy") {
    const prefill = store.get(PREFILL_KEY, null);
    if (prefill) {
      sessionStorage.removeItem(PREFILL_KEY);
      setTimeout(() => fillForm(prefill), 600);
    }
  }
  if (state.open || location.hash === "#ask") setOpen(true);
})();
