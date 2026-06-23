import { api } from "./api.js";

var loaded = false;
var loading = false;

function getElements() {
  return {
    screen: document.querySelector("#travel-screen"),
    list: document.querySelector("#travel-list"),
    status: document.querySelector("#travel-status"),
    refreshButton: document.querySelector("#travel-refresh-button"),
  };
}

function setTravelStatus(elements, text, isError) {
  if (!elements.status) {
    return;
  }
  elements.status.textContent = text;
  if (isError) {
    elements.status.classList.add("error");
  } else {
    elements.status.classList.remove("error");
  }
}

function normalizeDate(value) {
  if (typeof value !== "string" || !value) {
    return "未定";
  }
  return value;
}

function dateRange(trip) {
  return normalizeDate(trip.start_date) + " ～ " + normalizeDate(trip.end_date);
}

function clearNode(node) {
  while (node.firstChild) {
    node.removeChild(node.firstChild);
  }
}

function renderEmpty(elements) {
  clearNode(elements.list);
  var empty = document.createElement("p");
  empty.className = "travel-empty";
  empty.textContent = "旅行はまだありません。";
  elements.list.appendChild(empty);
}

function renderTrips(elements, trips) {
  var index;
  var trip;
  var row;
  var title;
  var dates;

  clearNode(elements.list);

  if (!trips.length) {
    renderEmpty(elements);
    return;
  }

  for (index = 0; index < trips.length; index += 1) {
    trip = trips[index] || {};
    row = document.createElement("article");
    row.className = "travel-trip-row";

    title = document.createElement("h4");
    title.textContent = trip.title || "無題の旅行";

    dates = document.createElement("p");
    dates.textContent = dateRange(trip);

    row.appendChild(title);
    row.appendChild(dates);
    elements.list.appendChild(row);
  }
}

function renderError(elements, message) {
  clearNode(elements.list);
  var error = document.createElement("p");
  error.className = "travel-error";
  error.textContent = message;
  elements.list.appendChild(error);
}

async function loadTravelTrips(force) {
  var elements = getElements();
  var data;

  if (!elements.screen || !elements.list) {
    return;
  }
  if (loading || (loaded && !force)) {
    return;
  }

  loading = true;
  setTravelStatus(elements, "読み込み中", false);

  try {
    data = await api("/api/travel/trips");
    renderTrips(elements, data.trips || []);
    loaded = true;
    setTravelStatus(elements, "取得済み", false);
  } catch (error) {
    renderError(elements, "旅行一覧を取得できませんでした。");
    setTravelStatus(elements, error.message, true);
  } finally {
    loading = false;
  }
}

function maybeLoadTravelTrips(force) {
  var elements = getElements();
  if (!elements.screen || elements.screen.hidden) {
    return;
  }
  loadTravelTrips(force);
}

function bindTravelScreen() {
  var elements = getElements();
  var travelButton = document.querySelector('[data-screen="travel-screen"]');

  if (elements.refreshButton) {
    elements.refreshButton.addEventListener("click", function () {
      loadTravelTrips(true);
    });
  }

  if (travelButton) {
    travelButton.addEventListener("click", function () {
      window.setTimeout(function () {
        maybeLoadTravelTrips(false);
      }, 0);
    });
  }

  window.addEventListener("hashchange", function () {
    window.setTimeout(function () {
      maybeLoadTravelTrips(false);
    }, 0);
  });

  window.setTimeout(function () {
    maybeLoadTravelTrips(false);
  }, 0);
}

if (document.readyState === "loading") {
  document.addEventListener("DOMContentLoaded", bindTravelScreen);
} else {
  bindTravelScreen();
}
