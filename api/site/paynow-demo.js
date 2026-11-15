/* Simulated "payment successful" screen for the buy flow's PayNow step (/paynow-demo/?t=<token>).
   The buy flow's QR opens this page, and opening it pays the demo payment: there is nothing to
   press. The buy flow, which checks every second, then finishes the purchase. (It also pays by
   itself after a few seconds, so the demo goes on when a phone cannot reach this server.)
   No real PayNow code, no money moves. */
"use strict";

const bankToken = new URLSearchParams(location.search).get("t") || "";
const bankUrl = (action = "") => `/api/premium-payments/${encodeURIComponent(bankToken)}${action}`;
const money = (sgd) => `S$${Number(sgd).toFixed(2)}`;

async function bankCall(url, method = "GET") {
  const response = await fetch(url, { method });
  const body = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(body.detail || `Request failed (${response.status})`);
  return body;
}

function make(tag, className, text) {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (text !== undefined) node.textContent = text;
  return node;
}

function row(label, value) {
  const line = make("div", "kv");
  line.append(make("span", "k", label), make("span", "v", value));
  return line;
}

const ENDED_TEXT = {
  cancelled: "This payment was cancelled. Go back to SafeDay for a new QR.",
  expired: "This payment request has expired. Go back to SafeDay for a new QR.",
};

function drawPayment(payment) {
  const body = document.getElementById("bank-body");
  const done = payment.status === "paid" || payment.status === "used";
  if (!done) {
    body.replaceChildren(make("p", "bank-done", ENDED_TEXT[payment.status] || payment.status));
    return;
  }
  const tick = make("div", "bank-tick", "✓");
  tick.setAttribute("aria-hidden", "true");
  body.replaceChildren(
    tick,
    make("h1", "", "Payment successful"),
    make("p", "bank-amount", money(payment.amount_sgd)),
    row("To", payment.payee),
    row("Reference", payment.reference),
    row("Paid by", "PayNow (simulated)"),
    make("p", "bank-done", "You can go back to SafeDay: your cover is being set up."),
  );
}

/** Opening this page is the payment. A payment already paid, by the demo timer or an earlier
    scan, is shown as successful too. */
async function payAndShow() {
  try {
    const payment = await bankCall(bankUrl());
    if (payment.status !== "pending") return drawPayment(payment);
    try {
      return drawPayment(await bankCall(bankUrl("/pay"), "POST"));
    } catch {
      return drawPayment(await bankCall(bankUrl()));  // paid in the meantime by the demo timer
    }
  } catch (failure) {
    document.getElementById("bank-body").replaceChildren(
      make("p", "error", `Could not open this payment: ${failure.message}`));
  }
}

payAndShow();
