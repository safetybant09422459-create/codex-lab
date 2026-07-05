import { api } from "./api.js";

var chatSending = false;
var chatComposing = false;
var currentContext = null;
var conversationHistory = [];
var maxConversationTurns = 5;
var chatSessionId =
  "web-" + Date.now().toString(36) + "-" + Math.random().toString(36).slice(2);

function rememberConversationTurn(role, content) {
  conversationHistory.push({ role: role, content: content.slice(0, 2000) });
  conversationHistory = conversationHistory.slice(-maxConversationTurns);
}

function chatElements() {
  return {
    form: document.querySelector("#chat-form"),
    history: document.querySelector("#chat-history"),
    input: document.querySelector("#chat-input"),
    submit: document.querySelector("#chat-submit"),
    status: document.querySelector("#chat-status"),
    suggestions: document.querySelector("#chat-suggestions"),
  };
}

function removeEmptyState(history) {
  var empty = history.querySelector("#chat-empty");
  if (empty) {
    empty.remove();
  }
}

function scrollChatToLatest(history) {
  history.scrollTop = history.scrollHeight;
}

function appendMessage(history, role, text, isError) {
  var row = document.createElement("div");
  var bubble = document.createElement("div");

  removeEmptyState(history);
  row.className = "chat-message " + role;
  bubble.className = "chat-bubble" + (isError ? " error" : "");
  bubble.textContent = text;
  row.appendChild(bubble);
  history.appendChild(row);
  scrollChatToLatest(history);
  return row;
}

function formatDate(value) {
  return typeof value === "string" && value ? value : "未定";
}

function formatPrefectures(value) {
  var parsed;

  if (Array.isArray(value)) {
    return value.filter(Boolean).join("・") || "未設定";
  }
  if (typeof value !== "string" || !value.trim()) {
    return "未設定";
  }
  try {
    parsed = JSON.parse(value);
    if (Array.isArray(parsed)) {
      return parsed.filter(Boolean).join("・") || "未設定";
    }
  } catch (_error) {
    // Storage may also contain a plain prefecture string.
  }
  return value;
}

function createTripCard(trip, includeLink) {
  var card = document.createElement("article");
  var title = document.createElement("h3");
  var dates = document.createElement("p");
  var prefectures = document.createElement("p");
  var memo;
  var link;

  trip = trip && typeof trip === "object" ? trip : {};
  card.className = "chat-trip-card";

  title.textContent = trip.title || "無題の旅行";
  dates.className = "chat-trip-meta";
  dates.textContent = formatDate(trip.start_date) + " ～ " + formatDate(trip.end_date);
  prefectures.className = "chat-trip-meta";
  prefectures.textContent = "行き先: " + formatPrefectures(trip.prefectures);

  card.appendChild(title);
  card.appendChild(dates);
  card.appendChild(prefectures);

  if (typeof trip.memo === "string" && trip.memo.trim()) {
    memo = document.createElement("p");
    memo.className = "chat-trip-memo";
    memo.textContent = trip.memo;
    card.appendChild(memo);
  }

  if (includeLink !== false) {
    link = document.createElement("a");
    link.className = "chat-trip-link";
    link.href = "#travel";
    link.textContent = "Travelで開く";
    if (typeof trip.id === "string") {
      link.dataset.tripId = trip.id;
    }
    card.appendChild(link);
  }
  return card;
}

function appendTrips(history, trips, includeLinks) {
  var wrapper;
  var list;
  var index;

  if (!Array.isArray(trips) || !trips.length) {
    return;
  }

  wrapper = document.createElement("div");
  wrapper.className = "chat-message assistant";
  list = document.createElement("div");
  list.className = "chat-trip-list";
  list.setAttribute("aria-label", "旅行一覧");

  for (index = 0; index < trips.length; index += 1) {
    list.appendChild(createTripCard(trips[index], includeLinks));
  }
  wrapper.appendChild(list);
  history.appendChild(wrapper);
  scrollChatToLatest(history);
}

function appendNavigation(history, navigation) {
  var wrapper;
  var link;

  if (
    !navigation ||
    typeof navigation !== "object" ||
    typeof navigation.target !== "string" ||
    !navigation.target
  ) {
    return;
  }

  wrapper = document.createElement("div");
  wrapper.className = "chat-message assistant chat-navigation";
  link = document.createElement("a");
  link.className = "chat-trip-link";
  link.href = navigation.target;
  link.textContent =
    typeof navigation.label === "string" && navigation.label
      ? navigation.label
      : "Travelで開く";
  if (typeof navigation.trip_id === "string") {
    link.dataset.tripId = navigation.trip_id;
  }
  wrapper.appendChild(link);
  history.appendChild(wrapper);
  scrollChatToLatest(history);
}

function setSending(elements, sending) {
  var chips = elements.suggestions.querySelectorAll("button");
  var index;

  chatSending = sending;
  elements.input.disabled = sending;
  elements.submit.disabled = sending;
  elements.submit.textContent = sending ? "送信中" : "送信";
  elements.status.textContent = sending ? "考え中..." : "";
  for (index = 0; index < chips.length; index += 1) {
    chips[index].disabled = sending;
  }
}

async function sendChat(elements, message) {
  var data;
  var historyForRequest;
  var assistantReply;

  message = typeof message === "string" ? message.trim() : "";
  if (!message || chatSending) {
    return;
  }

  historyForRequest = conversationHistory.slice(-maxConversationTurns);
  appendMessage(elements.history, "user", message, false);
  elements.input.value = "";
  setSending(elements, true);

  try {
    data = await api("/api/chat", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        message: message,
        session_id: chatSessionId,
        conversation_history: historyForRequest,
        context: currentContext,
      }),
    });
    if (Object.prototype.hasOwnProperty.call(data, "updated_context")) {
      currentContext =
        data.updated_context && typeof data.updated_context === "object"
          ? data.updated_context
          : null;
    }
    assistantReply =
      typeof data.reply === "string" && data.reply
        ? data.reply
        : "返答を受け取りました。";
    appendMessage(elements.history, "assistant", assistantReply, false);
    rememberConversationTurn("user", message);
    rememberConversationTurn("assistant", assistantReply);
    if (data.result && Array.isArray(data.result.trips)) {
      appendTrips(elements.history, data.result.trips);
    } else if (Array.isArray(data.candidates)) {
      appendTrips(elements.history, data.candidates, false);
    } else if (data.result && data.result.trip) {
      appendTrips(elements.history, [data.result.trip], false);
    }
    appendNavigation(elements.history, data.navigation);
  } catch (_error) {
    appendMessage(
      elements.history,
      "assistant",
      "うまく取得できませんでした",
      true,
    );
  } finally {
    setSending(elements, false);
    elements.input.focus();
  }
}

function bindChat() {
  var elements = chatElements();
  var chips;
  var index;

  if (!elements.form || elements.form.dataset.bound === "true") {
    return;
  }
  elements.form.dataset.bound = "true";

  elements.form.addEventListener("submit", function (event) {
    event.preventDefault();
    sendChat(elements, elements.input.value);
  });
  elements.input.addEventListener("compositionstart", function () {
    chatComposing = true;
  });
  elements.input.addEventListener("compositionend", function () {
    chatComposing = false;
  });
  elements.input.addEventListener("keydown", function (event) {
    if (
      event.key === "Enter" &&
      !event.shiftKey &&
      !event.isComposing &&
      !chatComposing &&
      event.keyCode !== 229
    ) {
      event.preventDefault();
      sendChat(elements, elements.input.value);
    }
  });

  chips = elements.suggestions.querySelectorAll("[data-chat-prompt]");
  for (index = 0; index < chips.length; index += 1) {
    chips[index].addEventListener("click", function () {
      elements.input.value = this.getAttribute("data-chat-prompt") || "";
      elements.input.focus();
    });
  }
}

if (document.readyState === "loading") {
  document.addEventListener("DOMContentLoaded", bindChat);
} else {
  bindChat();
}
