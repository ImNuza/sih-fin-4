/* The "payment successful" screen the buy flow's PayNow QR opens on the scanner's phone
   (/paynow-demo/?t=<token>&a=<amount>&r=<reference>). It is a demo: no money moves.

   The QR always points at the public site, so this page loads on any phone with internet, even
   when the buy flow runs on a laptop the phone cannot reach. The amount and reference come in
   the link, so the screen shows at once without this server. It then tells the server the
   payment went through; when the buy flow runs on the same site, the laptop moves on at once,
   and otherwise it moves on by itself after a few seconds. */
"use strict";

const params = new URLSearchParams(location.search);
const token = params.get("t") || "";
const payUrl = `/api/premium-payments/${encodeURIComponent(token)}/pay`;
const PAYEE = "Payung by Income";
const MAX_AMOUNT_SGD = 500;
const REFERENCE = /^PYP-[0-9A-F]{6}$/;

function make(tag, className, text) {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (text !== undefined) node.textContent = text;
  return node;
}

function row(label, value) {
  const line = make("div", "bank-row");
  line.append(make("span", "", label), make("b", "", value));
  return line;
}

/** The amount and reference from the link, or null if they are missing or not ours. */
function fromLink() {
  const amount = Number(params.get("a"));
  const reference = params.get("r") || "";
  if (!(amount > 0 && amount <= MAX_AMOUNT_SGD) || !REFERENCE.test(reference)) return null;
  return { amount, reference };
}

function paidAt() {
  return new Date().toLocaleString("en-SG", {
    day: "numeric", month: "short", year: "numeric", hour: "numeric", minute: "2-digit",
    timeZone: "Asia/Singapore",
  });
}

function showSuccess({ amount, reference }) {
  const tick = make("div", "bank-tick");
  tick.setAttribute("aria-hidden", "true");
  tick.innerHTML = '<svg viewBox="0 0 52 52"><path d="M14 27 l8 8 l16 -18" /></svg>';
  const card = make("section", "bank-receipt");
  card.append(
    row("To", PAYEE),
    row("Reference", reference),
    row("Paid by", "PayNow"),
    row("Date", paidAt()),
  );
  document.getElementById("bank-body").replaceChildren(
    tick,
    make("h1", "bank-title", "Payment successful"),
    make("p", "bank-amount", `S$${amount.toFixed(2)}`),
    card,
    make("p", "bank-done", "You can go back to Payung. Your cover is being set up."),
  );
}

function showProblem(text) {
  document.getElementById("bank-body").replaceChildren(make("p", "bank-done", text));
}

/** Tell the server the payment went through. Best effort: a laptop demo's payment lives on
    the laptop, not on this site, and pays itself there. */
function markPaid() {
  if (token) fetch(payUrl, { method: "POST" }).catch(() => {});
}

const payment = fromLink();
if (payment) {
  showSuccess(payment);
  markPaid();
} else {
  showProblem("This payment link is not complete. Go back to Payung and scan the QR again.");
}
