import { api } from "./api.js";

var loaded = false;
var loading = false;
var detailLoading = false;

function getElements() {
  return {
    screen: document.querySelector("#travel-screen"),
    list: document.querySelector("#travel-list"),
    detail: document.querySelector("#travel-detail"),
    detailContent: document.querySelector("#travel-detail-content"),
    status: document.querySelector("#travel-status"),
    refreshButton: document.querySelector("#travel-refresh-button"),
    backButton: document.querySelector("#travel-back-button"),
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

function formatTimelineTime(value) {
  var timeMatch;

  if (typeof value !== "string" || !value) {
    return "時刻未定";
  }

  timeMatch = value.match(/T(\d{2}):(\d{2})/);
  if (timeMatch) {
    return timeMatch[1] + ":" + timeMatch[2];
  }

  timeMatch = value.match(/^(\d{2}):(\d{2})/);
  if (timeMatch) {
    return timeMatch[1] + ":" + timeMatch[2];
  }

  return value;
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

function showList(elements) {
  if (elements.list) {
    elements.list.hidden = false;
  }
  if (elements.detail) {
    elements.detail.hidden = true;
  }
  if (elements.refreshButton) {
    elements.refreshButton.hidden = false;
  }
}

function showDetail(elements) {
  if (elements.list) {
    elements.list.hidden = true;
  }
  if (elements.detail) {
    elements.detail.hidden = false;
  }
  if (elements.refreshButton) {
    elements.refreshButton.hidden = true;
  }
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
    row = document.createElement("button");
    row.className = "travel-trip-row";
    row.type = "button";
    row.setAttribute("data-trip-id", trip.id || "");

    title = document.createElement("h4");
    title.textContent = trip.title || "無題の旅行";

    dates = document.createElement("p");
    dates.textContent = dateRange(trip);

    row.appendChild(title);
    row.appendChild(dates);
    row.addEventListener("click", function () {
      var tripId = this.getAttribute("data-trip-id");
      if (tripId) {
        loadTravelDetail(tripId);
      }
    });
    elements.list.appendChild(row);
  }
}

function renderTimelineItem(item) {
  var row = document.createElement("li");
  var time = document.createElement("time");
  var title = document.createElement("span");
  var titleText;

  item = item || {};
  titleText = item.display_title || item.place_name || item.memo || "無題";

  row.className = "travel-timeline-item";
  time.textContent = formatTimelineTime(item.start_at);
  title.textContent = titleText;

  row.appendChild(time);
  row.appendChild(title);
  return row;
}

function tripCoverImageUrl(trip) {
  var coverImage;

  if (!trip || typeof trip !== "object") {
    return "";
  }

  coverImage = trip.cover_image;
  if (!coverImage || typeof coverImage !== "object") {
    return "";
  }

  if (typeof coverImage.thumbnail_url === "string" && coverImage.thumbnail_url) {
    return coverImage.thumbnail_url;
  }
  if (typeof coverImage.url === "string" && coverImage.url) {
    return coverImage.url;
  }
  return "";
}

function showTravelCoverImageError(figure, text) {
  var errorNode;

  if (!figure) {
    return;
  }

  errorNode = document.createElement("div");
  errorNode.className = "photo-image-error";
  errorNode.textContent = text;
  figure.appendChild(errorNode);
}

function renderTripCoverImage(trip) {
  var imageUrl = tripCoverImageUrl(trip);
  var figure;
  var image;

  if (!imageUrl) {
    return null;
  }

  figure = document.createElement("figure");
  figure.className = "travel-cover-image";

  image = document.createElement("img");
  image.alt = (trip.title || "旅行") + " 代表写真";
  image.addEventListener("error", function () {
    showTravelCoverImageError(figure, "Image load error");
  });
  image.src = imageUrl;

  figure.appendChild(image);
  return figure;
}

function photoPreviewUrl(photo) {
  if (!photo || typeof photo !== "object") {
    return "";
  }
  if (typeof photo.preview_url === "string" && photo.preview_url) {
    return photo.preview_url;
  }
  if (typeof photo.thumbnail_url === "string" && photo.thumbnail_url) {
    return photo.thumbnail_url;
  }
  return "";
}

function showTravelPhotoImageError(card, text) {
  var errorNode;

  if (!card) {
    return;
  }

  errorNode = document.createElement("div");
  errorNode.className = "photo-image-error";
  errorNode.textContent = text;
  card.appendChild(errorNode);
}

function renderTravelPhotoCard(photo, trip) {
  var card = document.createElement("div");
  var link = document.createElement("a");
  var image = document.createElement("img");
  var thumbnailUrl = "";
  var previewUrl = "";
  var assetId = "";

  photo = photo || {};
  if (typeof photo.thumbnail_url === "string") {
    thumbnailUrl = photo.thumbnail_url;
  }
  previewUrl = photoPreviewUrl(photo);
  if (typeof photo.asset_id === "string") {
    assetId = photo.asset_id;
  }

  card.className = "travel-photo-card";
  if (!thumbnailUrl) {
    showTravelPhotoImageError(card, "Image unavailable");
    return card;
  }

  link.className = "travel-photo-link";
  link.href = previewUrl || thumbnailUrl;
  link.target = "_blank";
  link.rel = "noreferrer";
  if (assetId) {
    link.setAttribute("aria-label", assetId + " を開く");
  } else {
    link.setAttribute("aria-label", (trip.title || "旅行") + " の写真を開く");
  }

  image.alt = (trip.title || "旅行") + " の写真";
  image.addEventListener("error", function () {
    showTravelPhotoImageError(card, "Image load error");
  });
  image.src = thumbnailUrl;

  link.appendChild(image);
  card.appendChild(link);
  return card;
}

function renderTravelPhotosSection(trip, photos, photoError) {
  var section = document.createElement("section");
  var title = document.createElement("h4");
  var empty = document.createElement("p");
  var grid = document.createElement("div");
  var index;

  section.className = "travel-photos";
  title.className = "travel-photos-title";
  title.textContent = "Photos";
  section.appendChild(title);

  if (photoError) {
    empty.className = "travel-error";
    empty.textContent = "写真を取得できませんでした。";
    section.appendChild(empty);
    return section;
  }

  if (!photos || !photos.length) {
    empty.className = "travel-empty";
    empty.textContent = "写真はありません";
    section.appendChild(empty);
    return section;
  }

  grid.className = "travel-photo-grid";
  for (index = 0; index < photos.length && index < 20; index += 1) {
    grid.appendChild(renderTravelPhotoCard(photos[index], trip));
  }
  section.appendChild(grid);
  return section;
}

function renderTravelDetail(elements, data) {
  var trip = data.trip || {};
  var timeline = data.timeline || [];
  var photos = data.photos || [];
  var photoError = data.photoError || false;
  var coverImage = renderTripCoverImage(trip);
  var photosSection = renderTravelPhotosSection(trip, photos, photoError);
  var title = document.createElement("h3");
  var dates = document.createElement("p");
  var list = document.createElement("ol");
  var empty = document.createElement("p");
  var index;

  clearNode(elements.detailContent);

  title.className = "travel-detail-title";
  title.textContent = trip.title || "無題の旅行";
  dates.className = "travel-detail-dates";
  dates.textContent = dateRange(trip);
  list.className = "travel-timeline";

  if (coverImage) {
    elements.detailContent.appendChild(coverImage);
  }
  elements.detailContent.appendChild(photosSection);
  elements.detailContent.appendChild(title);
  elements.detailContent.appendChild(dates);

  if (!timeline.length) {
    empty.className = "travel-empty";
    empty.textContent = "タイムラインはまだありません。";
    elements.detailContent.appendChild(empty);
  } else {
    for (index = 0; index < timeline.length; index += 1) {
      list.appendChild(renderTimelineItem(timeline[index]));
    }
    elements.detailContent.appendChild(list);
  }

  showDetail(elements);
}

function renderError(elements, message) {
  clearNode(elements.list);
  var error = document.createElement("p");
  error.className = "travel-error";
  error.textContent = message;
  elements.list.appendChild(error);
}

function renderDetailError(elements, message) {
  var error;

  clearNode(elements.detailContent);
  error = document.createElement("p");
  error.className = "travel-error";
  error.textContent = message;
  elements.detailContent.appendChild(error);
  showDetail(elements);
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
    showList(elements);
    setTravelStatus(elements, "取得済み", false);
  } catch (error) {
    renderError(elements, "旅行一覧を取得できませんでした。");
    setTravelStatus(elements, error.message, true);
  } finally {
    loading = false;
  }
}

async function loadTravelDetail(tripId) {
  var elements = getElements();
  var data;
  var photoData;

  if (!elements.screen || !elements.detail || !elements.detailContent || detailLoading) {
    return;
  }

  detailLoading = true;
  setTravelStatus(elements, "詳細読み込み中", false);

  try {
    data = await api("/api/travel/trips/" + encodeURIComponent(tripId));
    try {
      photoData = await api(
        "/api/travel/trips/" + encodeURIComponent(tripId) + "/photos?limit=20"
      );
      data.photos = photoData.photos || [];
      data.photoError = false;
    } catch (photoError) {
      data.photos = [];
      data.photoError = true;
    }
    renderTravelDetail(elements, data);
    setTravelStatus(elements, "詳細取得済み", false);
  } catch (error) {
    if (error.message === "Travel trip not found") {
      renderDetailError(elements, "旅行が見つかりませんでした。");
    } else {
      renderDetailError(elements, "旅行詳細を取得できませんでした。");
    }
    setTravelStatus(elements, error.message, true);
  } finally {
    detailLoading = false;
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

  if (elements.backButton) {
    elements.backButton.addEventListener("click", function () {
      showList(getElements());
      setTravelStatus(getElements(), "取得済み", false);
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
