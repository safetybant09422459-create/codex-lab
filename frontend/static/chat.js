import { api } from "./api.js";

var chatSending = false;
var chatComposing = false;
var currentContext = null;
var conversationHistory = [];
var maxConversationTurns = 5;
var chatStorageKey = "jarvis.chat.working-context.v1";
var chatSessionId = createChatSessionId();

function createChatSessionId() {
  var bytes;
  var index;
  var randomPart = "";

  try {
    bytes = new Uint8Array(16);
    window.crypto.getRandomValues(bytes);
    for (index = 0; index < bytes.length; index += 1) {
      randomPart += bytes[index].toString(16).padStart(2, "0");
    }
  } catch (_error) {
    randomPart =
      Math.random().toString(36).slice(2) + Math.random().toString(36).slice(2);
  }
  return "web-" + Date.now().toString(36) + "-" + randomPart;
}

function readStoredChat() {
  var stored;
  var parsed;

  try {
    stored = window.sessionStorage.getItem(chatStorageKey);
    parsed = stored ? JSON.parse(stored) : null;
  } catch (_error) {
    return null;
  }
  if (!parsed || typeof parsed !== "object") {
    return null;
  }
  if (
    typeof parsed.session_id !== "string" ||
    !parsed.session_id ||
    parsed.session_id.length > 128 ||
    !Array.isArray(parsed.history)
  ) {
    return null;
  }
  return parsed;
}

function persistChat() {
  try {
    window.sessionStorage.setItem(
      chatStorageKey,
      JSON.stringify({
        session_id: chatSessionId,
        history: conversationHistory.slice(-maxConversationTurns),
      })
    );
  } catch (_error) {
    // Conversation remains usable when Safari storage is unavailable.
  }
}

function removeStoredChat() {
  try {
    window.sessionStorage.removeItem(chatStorageKey);
  } catch (_error) {
    // A new in-memory session still disconnects the cleared context.
  }
}

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
    clear: document.querySelector("#chat-clear"),
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
  if (isError) {
    row.setAttribute("role", "alert");
  }
  bubble.textContent = text;
  row.appendChild(bubble);
  history.appendChild(row);
  scrollChatToLatest(history);
  return row;
}

function appendChatError(history, message, retry) {
  var row = appendMessage(history, "assistant", message, true);
  var button;

  if (typeof retry !== "function") {
    return row;
  }
  button = document.createElement("button");
  button.className = "chat-retry";
  button.type = "button";
  button.textContent = "もう一度試す";
  button.addEventListener("click", function () {
    retry(row);
  });
  row.querySelector(".chat-bubble").appendChild(button);
  return row;
}

function chatErrorMessage(error) {
  if (error && error.code === "network_unavailable") {
    return window.navigator.onLine === false
      ? "オフラインのようです。接続を確認して、もう一度試してください。"
      : "Jarvisにつながりませんでした。少し待って、もう一度試してください。";
  }
  if (error && error.status === 429) {
    return "少し混み合っています。少し待ってから、もう一度試してください。";
  }
  if (error && error.status === 502) {
    return "今はうまく考えをまとめられませんでした。もう一度試してください。";
  }
  if (error && error.code === "chat_not_configured") {
    return "Jarvisの会話機能はまだ準備できていません。設定を確認してください。";
  }
  if (error && error.status === 422) {
    return "その内容は送れませんでした。短くして、もう一度試してください。";
  }
  return "うまく取得できませんでした。もう一度試してください。";
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
  elements.clear.disabled = sending;
  elements.history.setAttribute("aria-busy", sending ? "true" : "false");
  elements.submit.textContent = sending ? "送信中" : "送信";
  elements.status.textContent = sending ? "考え中..." : "";
  for (index = 0; index < chips.length; index += 1) {
    chips[index].disabled = sending;
  }
}

function restoreChat(elements) {
  var stored = readStoredChat();
  var restoredHistory = [];
  var index;
  var turn;

  if (!stored) {
    return;
  }
  chatSessionId = stored.session_id;
  stored.history = stored.history.slice(-maxConversationTurns);
  for (index = 0; index < stored.history.length; index += 1) {
    turn = stored.history[index];
    if (
      turn &&
      (turn.role === "user" || turn.role === "assistant") &&
      typeof turn.content === "string"
    ) {
      restoredHistory.push({
        role: turn.role,
        content: turn.content.slice(0, 2000),
      });
    }
  }
  conversationHistory = restoredHistory;
  for (index = 0; index < conversationHistory.length; index += 1) {
    turn = conversationHistory[index];
    appendMessage(elements.history, turn.role, turn.content, false);
  }
}

async function clearChat(elements) {
  var previousSessionId;

  if (chatSending || !window.confirm("このタブの会話を消しますか？")) {
    return;
  }
  previousSessionId = chatSessionId;
  chatSessionId = createChatSessionId();
  conversationHistory = [];
  currentContext = null;
  removeStoredChat();
  elements.history.textContent = "";
  appendMessage(
    elements.history,
    "assistant",
    "会話を消しました。新しく話しかけてください。",
    false
  );
  elements.status.textContent = "会話を消しました";
  try {
    await api("/api/chat/session/reset", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ session_id: previousSessionId }),
    });
  } catch (_error) {
    elements.status.textContent =
      "このタブの会話は消去済みです。サーバー側の一時状態は再起動時にも破棄されます。";
  }
  elements.input.focus();
}

async function sendChat(elements, message) {
  var data;
  var historyForRequest;
  var assistantReply;
  var userRow;

  message = typeof message === "string" ? message.trim() : "";
  if (!message || chatSending) {
    return;
  }

  historyForRequest = conversationHistory.slice(-maxConversationTurns);
  userRow = appendMessage(elements.history, "user", message, false);
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
    persistChat();
    if (data.result && Array.isArray(data.result.trips)) {
      appendTrips(elements.history, data.result.trips);
    } else if (Array.isArray(data.candidates)) {
      appendTrips(elements.history, data.candidates, false);
    } else if (data.result && data.result.trip) {
      appendTrips(elements.history, [data.result.trip], false);
    }
    appendNavigation(elements.history, data.navigation);
  } catch (error) {
    var errorMessage = chatErrorMessage(error);
    appendChatError(
      elements.history,
      errorMessage,
      error && error.retryable
        ? function (errorRow) {
            userRow.remove();
            errorRow.remove();
            sendChat(elements, message);
          }
        : null
    );
    elements.status.textContent = errorMessage;
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
  restoreChat(elements);

  elements.form.addEventListener("submit", function (event) {
    event.preventDefault();
    sendChat(elements, elements.input.value);
  });
  elements.clear.addEventListener("click", function () {
    clearChat(elements);
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
