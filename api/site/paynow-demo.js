/* Simulated bank screen for the buy flow's PayNow step (/paynow-demo/?t=<token>).
   The buy flow's QR opens this page. "Pay" marks the demo payment paid; the buy flow, which
   checks every few seconds, then finishes the purchase. No real PayNow code, no money moves. */
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

function row(label, value) {
  const line = document.createElement("div");
  line.className = "kv";
  const k = document.createElement("span");
  k.className = "k";
  k.textContent = label;
  const v = document.createElement("span");
  v.className = "v";
  v.textContent = value;
  line.append(k, v);
  return line;
}

function message(text, tone = "fine") {
  const p = document.createElement("p");
  p.className = tone;
  p.textContent = text;
  return p;
}

const DONE_TEXT = {
  paid: "Paid. You can go back to SafeDay: your cover is being set up.",
  used: "This payment has gone through and your cover is set up.",
  cancelled: "You cancelled this payment. Go back to SafeDay for a new QR.",
  expired: "This payment request has expired. Go back to SafeDay for a new QR.",
};

function drawPayment(payment) {
  const body = document.getElementById("bank-body");
  const amount = document.createElement("p");
  amount.className = "bank-amount";
  amount.textContent = money(payment.amount_sgd);
  const parts = [
    amount,
    row("To", payment.payee),
    row("Reference", payment.reference),
    row("From", "Your account (simulated)"),
  ];
  if (payment.status !== "pending") {
    body.replaceChildren(...parts, message(DONE_TEXT[payment.status] || payment.status, "bank-done"));
    return;
  }
  const pay = document.createElement("button");
  pay.className = "btn primary";
  pay.type = "button";
  pay.textContent = `Pay ${money(payment.amount_sgd)}`;
  const cancel = document.createElement("button");
  cancel.className = "btn quiet";
  cancel.type = "button";
  cancel.textContent = "Cancel";
  const actions = document.createElement("div");
  actions.className = "bank-actions";
  actions.append(pay, cancel);
  const error = message("", "error");
  const act = (action) => async () => {
    pay.disabled = cancel.disabled = true;
    try {
      drawPayment(await bankCall(bankUrl(action), "POST"));
    } catch (failure) {
      error.textContent = failure.message;
      pay.disabled = cancel.disabled = false;
    }
  };
  pay.addEventListener("click", act("/pay"));
  cancel.addEventListener("click", act("/cancel"));
  body.replaceChildren(...parts, actions, error);
}

async function loadPayment() {
  try {
    drawPayment(await bankCall(bankUrl()));
  } catch (failure) {
    document.getElementById("bank-body").replaceChildren(
      message(`Could not open this payment: ${failure.message}`, "error"));
  }
}

loadPayment();
