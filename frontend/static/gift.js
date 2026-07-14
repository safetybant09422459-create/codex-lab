import { api } from "./api.js";

var loaded = false;
var activeType = "";

function getElements() {
  return {
    screen: document.querySelector("#gift-screen"),
    list: document.querySelector("#gift-list"),
    status: document.querySelector("#gift-status"),
    add: document.querySelector("#gift-add-button"),
    panel: document.querySelector("#gift-form-panel"),
    cancel: document.querySelector("#gift-cancel-button"),
    form: document.querySelector("#gift-form"),
    type: document.querySelector("#gift-entry-type"),
    title: document.querySelector("#gift-title"),
    giver: document.querySelector("#gift-giver"),
    recipient: document.querySelector("#gift-recipient"),
    date: document.querySelector("#gift-date"),
    amount: document.querySelector("#gift-amount"),
    event: document.querySelector("#gift-event"),
    occasionDate: document.querySelector("#gift-occasion-date"),
    memo: document.querySelector("#gift-memo"),
  };
}

function typeLabel(value) {
  return { candidate: "候補", given: "贈った", received: "もらった" }[value] || value;
}

function entryCard(entry) {
  var card = document.createElement("article");
  var head = document.createElement("div");
  var badge = document.createElement("span");
  var title = document.createElement("h3");
  var meta = document.createElement("p");
  var details = [];
  card.className = "gift-card";
  head.className = "gift-card-head";
  badge.className = "gift-badge " + entry.entry_type;
  badge.textContent = typeLabel(entry.entry_type);
  title.textContent = entry.title;
  head.appendChild(badge);
  head.appendChild(title);
  card.appendChild(head);
  if (entry.giver || entry.recipient) details.push((entry.giver || "未記録") + " → " + (entry.recipient || "未記録"));
  if (entry.gift_date) details.push(entry.gift_date);
  if (entry.amount_yen !== null && entry.amount_yen !== undefined) details.push(Number(entry.amount_yen).toLocaleString("ja-JP") + "円");
  if (entry.related_event) details.push(entry.related_event);
  meta.className = "gift-meta";
  meta.textContent = details.join(" ・ ") || "詳細はまだありません";
  card.appendChild(meta);
  if (entry.memo) {
    var memo = document.createElement("p");
    memo.className = "gift-memo";
    memo.textContent = entry.memo;
    card.appendChild(memo);
  }
  return card;
}

async function loadGifts(force) {
  var el = getElements();
  if (!el.screen || el.screen.hidden || (loaded && !force)) return;
  el.status.textContent = "読み込み中…";
  el.status.classList.remove("error");
  try {
    var query = activeType ? "?entry_type=" + encodeURIComponent(activeType) : "";
    var data = await api("/api/gifts" + query);
    el.list.replaceChildren();
    data.entries.forEach(function (entry) { el.list.appendChild(entryCard(entry)); });
    if (!data.entries.length) {
      var empty = document.createElement("p");
      empty.className = "gift-empty";
      empty.textContent = activeType === "candidate" ? "候補はまだありません。思いついた時に記録できます。" : "記録はまだありません。最初のGiftを残してみましょう。";
      el.list.appendChild(empty);
    }
    el.status.textContent = data.count + "件";
    loaded = true;
  } catch (error) {
    el.status.textContent = error.message;
    el.status.classList.add("error");
  }
}

function payload(el) {
  var amount = el.amount.value.trim();
  var data = { entry_type: el.type.value, title: el.title.value.trim() };
  [["giver", el.giver], ["recipient", el.recipient], ["gift_date", el.date], ["memo", el.memo], ["related_event", el.event], ["occasion_date", el.occasionDate]].forEach(function (pair) {
    var value = pair[1].value.trim();
    if (value) data[pair[0]] = value;
  });
  if (amount) data.amount_yen = Number(amount);
  return data;
}

function bind() {
  var el = getElements();
  if (!el.screen) return;
  el.add.addEventListener("click", function () { el.panel.hidden = false; el.title.focus(); });
  el.cancel.addEventListener("click", function () { el.panel.hidden = true; });
  document.querySelectorAll(".gift-filter").forEach(function (button) {
    button.addEventListener("click", function () {
      document.querySelectorAll(".gift-filter").forEach(function (item) { item.classList.remove("active"); });
      button.classList.add("active");
      activeType = button.getAttribute("data-gift-type") || "";
      loaded = false;
      loadGifts(true);
    });
  });
  el.form.addEventListener("submit", async function (event) {
    event.preventDefault();
    var data = payload(el);
    if ((data.entry_type === "given" || data.entry_type === "received") && (!data.giver || !data.recipient || !data.gift_date)) {
      el.status.textContent = "贈った・もらった記録には、誰から・誰へ・日付が必要です。";
      el.status.classList.add("error");
      return;
    }
    if (!window.confirm("「" + data.title + "」をGiftに保存しますか？")) return;
    try {
      await api("/api/gifts", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(data) });
      el.form.reset();
      el.panel.hidden = true;
      loaded = false;
      await loadGifts(true);
    } catch (error) {
      el.status.textContent = error.message;
      el.status.classList.add("error");
    }
  });
  window.addEventListener("jarvis:screenchange", function (event) {
    if (event.detail && event.detail.screenId === "gift-screen") window.setTimeout(function () { loadGifts(false); }, 0);
  });
  window.setTimeout(function () { loadGifts(false); }, 0);
}

if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", bind);
else bind();
