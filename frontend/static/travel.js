import { api } from "./api.js";

var loaded = false;
var loading = false;
var detailLoading = false;
var currentTripDetailData = null;
var currentTravelView = "list";
var experiencePhotosPageSize = 20;
var experiencePhotosLoading = false;
var experiencePhotoLinkLoading = false;
var experienceStatusOptions = ["planned", "completed", "skipped", "archived"];
var experienceCreateStatusOptions = ["planned", "completed", "skipped"];
var experienceCreateTypeOptions = ["spot", "move", "event", "memo"];

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
  currentTravelView = "list";
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

function experienceTitle(experience) {
  experience = experience || {};
  return experience.display_title || experience.place_name || experience.memo || "無題";
}

function spotTitle(spot) {
  return experienceTitle(spot);
}

function experienceTypeLabel(experience) {
  var type;

  experience = experience || {};
  type = experience.experience_type || experience.item_type || "spot";
  if (type === "move") {
    return "Move";
  }
  if (type === "event") {
    return "Event";
  }
  if (type === "memo") {
    return "Memo";
  }
  return "Spot";
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
  var button = document.createElement("button");
  var time = document.createElement("time");
  var title = document.createElement("span");
  var titleText;

  item = item || {};
  titleText = experienceTitle(item);

  row.className = "travel-timeline-item";
  button.className = "travel-timeline-link";
  button.type = "button";
  button.setAttribute("data-experience-id", item.experience_id || item.id || "");
  button.setAttribute("data-spot-id", item.timeline_item_id || item.id || "");
  time.textContent = formatTimelineTime(item.start_at);
  title.textContent = titleText;

  button.appendChild(time);
  button.appendChild(title);
  button.addEventListener("click", function () {
    var experienceId = this.getAttribute("data-experience-id");
    if (experienceId) {
      loadExperienceDetail(experienceId);
    }
  });
  row.appendChild(button);
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

function renderTravelPhotoCard(photo, trip, options) {
  var card = document.createElement("div");
  var link = document.createElement("a");
  var image = document.createElement("img");
  var badges = document.createElement("div");
  var badge;
  var actions;
  var linkButton;
  var coverButton;
  var hideButton;
  var thumbnailUrl = "";
  var previewUrl = "";
  var assetId = "";
  var state = "";

  photo = photo || {};
  options = options || {};
  state = options.experiencePhotoState || "candidate";
  if (typeof photo.thumbnail_url === "string") {
    thumbnailUrl = photo.thumbnail_url;
  }
  previewUrl = photoPreviewUrl(photo);
  if (typeof photo.asset_id === "string") {
    assetId = photo.asset_id;
  }

  card.className = "travel-photo-card";
  trip = trip || {};
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

  if (options.showExperienceState) {
    badges.className = "travel-photo-badges";
    badge = document.createElement("span");
    badge.className = "travel-photo-badge";
    if (state === "cover") {
      badge.className += " cover";
      badge.textContent = "カバー";
    } else if (state === "linked") {
      badge.className += " linked";
      badge.textContent = "リンク済み";
    } else {
      badge.textContent = "候補";
    }
    badges.appendChild(badge);
    card.appendChild(badges);
  }

  if (options.showLinkActions && assetId) {
    actions = document.createElement("div");
    linkButton = document.createElement("button");
    coverButton = document.createElement("button");
    hideButton = document.createElement("button");

    actions.className = "travel-photo-actions";

    linkButton.type = "button";
    linkButton.className = "travel-photo-action";
    linkButton.textContent = state === "candidate" ? "採用" : "採用済み";
    linkButton.disabled = !!options.linkBusy || state === "linked" || state === "cover";
    linkButton.addEventListener("click", function () {
      linkExperiencePhoto(options.elements, options.data, assetId, "linked");
    });
    actions.appendChild(linkButton);

    coverButton.type = "button";
    coverButton.className = "travel-photo-action secondary";
    coverButton.textContent = "カバーにする";
    coverButton.disabled = !!options.linkBusy || state === "cover";
    coverButton.addEventListener("click", function () {
      linkExperiencePhoto(options.elements, options.data, assetId, "cover");
    });
    actions.appendChild(coverButton);

    hideButton.type = "button";
    hideButton.className = "travel-photo-action secondary";
    hideButton.textContent = "候補から外す";
    hideButton.disabled = !!options.linkBusy;
    hideButton.addEventListener("click", function () {
      hideExperiencePhotoCandidate(options.elements, options.data, assetId);
    });
    actions.appendChild(hideButton);

    card.appendChild(actions);
  }
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

function experiencePhotoPagination(data) {
  if (!data || typeof data !== "object" || !data.pagination) {
    return {};
  }
  return data.pagination;
}

function experiencePhotosHasMore(photos, pagination, limit) {
  if (pagination && typeof pagination.has_more === "boolean") {
    return pagination.has_more;
  }
  if (!photos) {
    return false;
  }
  return photos.length === limit;
}

function appendExperiencePhotos(data, pageData) {
  var photos = pageData.photos || [];
  var index;

  if (!data.photos) {
    data.photos = [];
  }
  for (index = 0; index < photos.length; index += 1) {
    data.photos.push(photos[index]);
  }
  data.pagination = pageData.pagination || {
    limit: pageData.limit,
    offset: pageData.offset,
    count: photos.length,
    has_more: pageData.has_more,
  };
  data.experiencePhotosHasMore = experiencePhotosHasMore(
    photos,
    data.pagination,
    data.experiencePhotosLimit || experiencePhotosPageSize
  );
}

function photoAssetId(photo) {
  if (photo && typeof photo.asset_id === "string" && photo.asset_id) {
    return photo.asset_id;
  }
  if (photo && typeof photo.photo_asset_id === "string" && photo.photo_asset_id) {
    return photo.photo_asset_id;
  }
  return "";
}

function activeExperiencePhotoLinks(data) {
  var links = data.photoLinks || data.photo_links || [];
  var activeLinks = [];
  var index;

  for (index = 0; index < links.length; index += 1) {
    if (!links[index].status || links[index].status === "active") {
      activeLinks.push(links[index]);
    }
  }
  return activeLinks;
}

function linkedPhotoAssetMap(data) {
  var links = activeExperiencePhotoLinks(data);
  var map = {};
  var assetId;
  var index;

  for (index = 0; index < links.length; index += 1) {
    assetId = photoAssetId(links[index]);
    if (assetId) {
      map[assetId] = true;
    }
  }
  return map;
}

function experiencePhotoLinkStateMap(data) {
  var links = activeExperiencePhotoLinks(data);
  var map = {};
  var assetId;
  var index;

  for (index = 0; index < links.length; index += 1) {
    assetId = photoAssetId(links[index]);
    if (assetId) {
      if (links[index].link_type === "cover") {
        map[assetId] = "cover";
      } else if (!map[assetId]) {
        map[assetId] = "linked";
      }
    }
  }
  return map;
}

function experiencePhotoState(data, photo) {
  var assetId = photoAssetId(photo);
  var stateMap = experiencePhotoLinkStateMap(data);

  if (assetId && stateMap[assetId]) {
    return stateMap[assetId];
  }
  return "candidate";
}

function isExperiencePhotoAlreadyLinked(data, photo) {
  var assetId = photoAssetId(photo);
  var linkedMap = linkedPhotoAssetMap(data);
  return !!(assetId && linkedMap[assetId]);
}

function isExperiencePhotoCandidateHidden(data, photo) {
  var assetId = photoAssetId(photo);
  var hidden = data.hiddenExperiencePhotoCandidates || {};
  return !!(assetId && hidden[assetId]);
}

function mergeExperiencePhotoLink(data, link) {
  var links;
  var index;

  if (!data || !link || typeof link !== "object") {
    return;
  }
  if (!data.photoLinks) {
    data.photoLinks = [];
  }
  links = data.photoLinks;

  if (link.link_type === "cover") {
    for (index = 0; index < links.length; index += 1) {
      if (links[index].link_type === "cover" && links[index].status === "active") {
        links[index].status = "archived";
      }
    }
  }

  for (index = 0; index < links.length; index += 1) {
    if (links[index].id && link.id && links[index].id === link.id) {
      links[index] = link;
      return;
    }
  }
  links.push(link);
}

function hideExperiencePhotoCandidate(elements, data, assetId) {
  if (!data.hiddenExperiencePhotoCandidates) {
    data.hiddenExperiencePhotoCandidates = {};
  }
  if (assetId) {
    data.hiddenExperiencePhotoCandidates[assetId] = true;
    renderExperienceDetail(elements, data);
    setTravelStatus(elements, "候補から外しました", false);
  }
}

function renderOutOfRangePhotoLinkNotice(elements, data) {
  var section = document.createElement("section");
  var title = document.createElement("h4");
  var button = document.createElement("button");
  var message = document.createElement("p");

  section.className = "travel-photos travel-out-of-range-photos";
  title.className = "travel-photos-title";
  title.textContent = "期間外写真";
  button.type = "button";
  button.className = "travel-experience-photo-more";
  button.textContent = "期間外写真を探す";
  message.className = "travel-muted";
  message.hidden = true;
  message.textContent = "期間外写真検索は未実装です。";
  button.addEventListener("click", function () {
    message.hidden = false;
    setTravelStatus(elements, "期間外写真検索は未実装です", false);
  });

  section.appendChild(title);
  section.appendChild(button);
  section.appendChild(message);
  return section;
}

function renderExperienceLinkedPhotosSection(elements, data) {
  var section = document.createElement("section");
  var title = document.createElement("h4");
  var empty = document.createElement("p");
  var grid = document.createElement("div");
  var links = activeExperiencePhotoLinks(data);
  var experience = data.experience || data.spot || {};
  var state;
  var index;

  section.className = "travel-photos travel-linked-photos";
  title.className = "travel-photos-title";
  title.textContent = "リンク済み写真・カバー写真";
  section.appendChild(title);

  if (!links.length) {
    empty.className = "travel-empty";
    empty.textContent = "リンク済み写真はありません";
    section.appendChild(empty);
    return section;
  }

  grid.className = "travel-photo-grid";
  for (index = 0; index < links.length; index += 1) {
    state = links[index].link_type === "cover" ? "cover" : "linked";
    grid.appendChild(
      renderTravelPhotoCard(
        links[index],
        { title: experienceTitle(experience) },
        {
          showExperienceState: true,
          experiencePhotoState: state,
        }
      )
    );
  }
  section.appendChild(grid);
  return section;
}

function renderExperiencePhotoControls(elements, data) {
  var controls = document.createElement("div");
  var moreButton = document.createElement("button");
  var photos = data.photos || [];

  controls.className = "travel-experience-photo-controls";
  moreButton.type = "button";
  moreButton.className = "travel-experience-photo-more";
  moreButton.textContent = "もっと見る";
  moreButton.disabled = experiencePhotosLoading;
  moreButton.hidden = !data.experiencePhotosHasMore;
  moreButton.addEventListener("click", function () {
    loadExperiencePhotosPage(
      elements,
      data,
      photos.length,
      data.experiencePhotosLimit || experiencePhotosPageSize
    );
  });

  controls.appendChild(moreButton);
  return controls;
}

function renderExperiencePhotosSection(elements, data) {
  var section = document.createElement("section");
  var title = document.createElement("h4");
  var empty = document.createElement("p");
  var grid = document.createElement("div");
  var photos = data.photos || [];
  var experience = data.experience || data.spot || {};
  var renderedCount = 0;
  var photoState;
  var index;

  section.className = "travel-photos travel-experience-photos";
  title.className = "travel-photos-title";
  title.textContent = "候補写真";
  section.appendChild(title);

  if (data.photoError || data.photo_error) {
    empty.className = "travel-error";
    empty.textContent = "写真を取得できませんでした。";
    section.appendChild(empty);
    return section;
  }

  if (!photos.length) {
    empty.className = "travel-empty";
    empty.textContent = "候補写真はありません";
    section.appendChild(empty);
  } else {
    grid.className = "travel-photo-grid";
    for (index = 0; index < photos.length; index += 1) {
      if (!isExperiencePhotoCandidateHidden(data, photos[index])) {
        photoState = experiencePhotoState(data, photos[index]);
        grid.appendChild(
          renderTravelPhotoCard(
            photos[index],
            { title: experienceTitle(experience) },
            {
              showLinkActions: true,
              showExperienceState: true,
              experiencePhotoState: photoState,
              elements: elements,
              data: data,
              linkBusy: experiencePhotoLinkLoading,
            }
          )
        );
        renderedCount += 1;
      }
    }
    if (renderedCount === 0) {
      empty.className = "travel-empty";
      empty.textContent = "表示中の候補写真はありません";
      section.appendChild(empty);
    } else {
      section.appendChild(grid);
    }
  }

  section.appendChild(renderExperiencePhotoControls(elements, data));
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
  var createActions = document.createElement("div");
  var createButton = document.createElement("button");
  var index;

  clearNode(elements.detailContent);
  currentTripDetailData = data;
  currentTravelView = "trip";
  if (elements.backButton) {
    elements.backButton.textContent = "一覧へ戻る";
  }

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

  createActions.className = "travel-experience-create-actions";
  createButton.type = "button";
  createButton.className = "travel-experience-create-button";
  createButton.textContent = "＋体験追加";
  createButton.addEventListener("click", function () {
    renderExperienceCreateForm(elements, data, "");
  });
  createActions.appendChild(createButton);
  elements.detailContent.appendChild(createActions);

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

function renderExperienceCreateError(form, message) {
  var error = form.querySelector(".travel-experience-create-error");

  if (!error) {
    return;
  }
  error.textContent = message || "";
  error.hidden = !message;
}

function renderExperienceCreateForm(elements, data, errorText) {
  var trip = data.trip || {};
  var tripId = trip.id || data.trip_id || "";
  var form = document.createElement("form");
  var typeField = document.createElement("div");
  var typeLabel = document.createElement("label");
  var typeSelect = document.createElement("select");
  var titleField = document.createElement("div");
  var titleLabel = document.createElement("label");
  var titleInput = document.createElement("input");
  var memoField = document.createElement("div");
  var memoLabel = document.createElement("label");
  var memoInput = document.createElement("textarea");
  var statusField = document.createElement("div");
  var statusLabel = document.createElement("label");
  var statusSelect = document.createElement("select");
  var error = document.createElement("p");
  var actions = document.createElement("div");
  var saveButton = document.createElement("button");
  var cancelButton = document.createElement("button");
  var index;

  clearNode(elements.detailContent);
  currentTravelView = "experience-create";
  if (elements.backButton) {
    elements.backButton.textContent = "旅行へ戻る";
  }

  form.className = "travel-experience-create-form";
  form.setAttribute("data-trip-id", tripId);

  typeField.className = "travel-experience-create-field";
  typeLabel.setAttribute("for", "travel-experience-create-type");
  typeLabel.textContent = "type";
  typeSelect.id = "travel-experience-create-type";
  typeSelect.name = "experience_type";
  for (index = 0; index < experienceCreateTypeOptions.length; index += 1) {
    appendExperienceStatusOption(typeSelect, experienceCreateTypeOptions[index]);
  }
  typeField.appendChild(typeLabel);
  typeField.appendChild(typeSelect);

  titleField.className = "travel-experience-create-field";
  titleLabel.setAttribute("for", "travel-experience-create-display-title");
  titleLabel.textContent = "title";
  titleInput.id = "travel-experience-create-display-title";
  titleInput.name = "display_title";
  titleInput.required = true;
  titleField.appendChild(titleLabel);
  titleField.appendChild(titleInput);

  memoField.className = "travel-experience-create-field";
  memoLabel.setAttribute("for", "travel-experience-create-memo");
  memoLabel.textContent = "memo";
  memoInput.id = "travel-experience-create-memo";
  memoInput.name = "memo";
  memoField.appendChild(memoLabel);
  memoField.appendChild(memoInput);

  statusField.className = "travel-experience-create-field";
  statusLabel.setAttribute("for", "travel-experience-create-status");
  statusLabel.textContent = "status";
  statusSelect.id = "travel-experience-create-status";
  statusSelect.name = "status";
  for (index = 0; index < experienceCreateStatusOptions.length; index += 1) {
    appendExperienceStatusOption(statusSelect, experienceCreateStatusOptions[index]);
  }
  statusSelect.value = "planned";
  statusField.appendChild(statusLabel);
  statusField.appendChild(statusSelect);

  error.className = "travel-error travel-experience-create-error";
  error.hidden = true;

  actions.className = "travel-experience-create-actions";
  saveButton.type = "submit";
  saveButton.textContent = "保存";
  cancelButton.type = "button";
  cancelButton.textContent = "キャンセル";
  cancelButton.addEventListener("click", function () {
    cancelExperienceCreate(elements, data);
  });
  actions.appendChild(saveButton);
  actions.appendChild(cancelButton);

  form.appendChild(typeField);
  form.appendChild(titleField);
  form.appendChild(memoField);
  form.appendChild(statusField);
  form.appendChild(error);
  form.appendChild(actions);
  form.addEventListener("submit", function (event) {
    submitExperienceCreate(event, elements, data);
  });

  elements.detailContent.appendChild(form);
  renderExperienceCreateError(form, errorText);
  showDetail(elements);
}

function cancelExperienceCreate(elements, data) {
  renderTravelDetail(elements, data);
}

async function submitExperienceCreate(event, elements, data) {
  var form = event.target;
  var tripId = form.getAttribute("data-trip-id");
  var saveButton = form.querySelector('button[type="submit"]');
  var payload;
  var response;
  var experienceId;

  event.preventDefault();
  if (!tripId) {
    renderExperienceCreateError(form, "Trip IDが見つかりませんでした。");
    return;
  }

  payload = {
    experience_type: form.elements.experience_type.value,
    display_title: form.elements.display_title.value,
    memo: form.elements.memo.value,
    status: form.elements.status.value,
  };

  if (saveButton) {
    saveButton.disabled = true;
  }
  setTravelStatus(elements, "Experience作成中", false);

  try {
    response = await api(
      "/api/travel/trips/" + encodeURIComponent(tripId) + "/experiences",
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      }
    );
    await loadTravelDetail(tripId);
    experienceId = response.experience_id;
    if (experienceId) {
      await loadExperienceDetail(experienceId);
    }
    setTravelStatus(elements, "Experience作成済み", false);
  } catch (error) {
    renderExperienceCreateError(
      form,
      error.message || "Experienceを作成できませんでした。"
    );
    setTravelStatus(elements, error.message, true);
  } finally {
    if (saveButton) {
      saveButton.disabled = false;
    }
  }
}

function renderSpotMeta(labelText, valueText) {
  var row = document.createElement("p");
  var label = document.createElement("strong");
  var value = document.createElement("span");

  row.className = "travel-spot-meta";
  label.textContent = labelText;
  value.textContent = valueText || "未定";
  row.appendChild(label);
  row.appendChild(value);
  return row;
}

function appendExperienceStatusOption(select, value) {
  var option = document.createElement("option");
  option.value = value;
  option.textContent = value;
  select.appendChild(option);
}

function renderExperienceActions(elements, data) {
  var actions = document.createElement("div");
  var editButton = document.createElement("button");

  actions.className = "travel-experience-actions";
  editButton.type = "button";
  editButton.className = "travel-experience-edit-button";
  editButton.textContent = "編集";
  editButton.addEventListener("click", function () {
    renderExperienceEditForm(elements, data, "");
  });

  actions.appendChild(editButton);
  return actions;
}

function renderExperienceEditError(form, message) {
  var error = form.querySelector(".travel-experience-edit-error");

  if (!error) {
    return;
  }
  error.textContent = message || "";
  error.hidden = !message;
}

function experienceStatusIsKnown(status) {
  var index;

  for (index = 0; index < experienceStatusOptions.length; index += 1) {
    if (experienceStatusOptions[index] === status) {
      return true;
    }
  }
  return false;
}

function experienceIdFromData(data) {
  var experience = data.experience || data.spot || {};

  return data.experience_id || experience.experience_id || experience.id || "";
}

function renderExperienceEditForm(elements, data, errorText) {
  var experience = data.experience || data.spot || {};
  var form = document.createElement("form");
  var titleField = document.createElement("div");
  var titleLabel = document.createElement("label");
  var titleInput = document.createElement("input");
  var memoField = document.createElement("div");
  var memoLabel = document.createElement("label");
  var memoInput = document.createElement("textarea");
  var statusField = document.createElement("div");
  var statusLabel = document.createElement("label");
  var statusSelect = document.createElement("select");
  var error = document.createElement("p");
  var actions = document.createElement("div");
  var saveButton = document.createElement("button");
  var cancelButton = document.createElement("button");
  var status = experience.status || "";
  var index;

  clearNode(elements.detailContent);
  currentTravelView = "experience";
  if (elements.backButton) {
    elements.backButton.textContent = "旅行へ戻る";
  }

  form.className = "travel-experience-edit-form";
  form.setAttribute("data-experience-id", experienceIdFromData(data));

  titleField.className = "travel-experience-edit-field";
  titleLabel.setAttribute("for", "travel-experience-display-title");
  titleLabel.textContent = "title";
  titleInput.id = "travel-experience-display-title";
  titleInput.name = "display_title";
  titleInput.value = experience.display_title || "";
  titleField.appendChild(titleLabel);
  titleField.appendChild(titleInput);

  memoField.className = "travel-experience-edit-field";
  memoLabel.setAttribute("for", "travel-experience-memo");
  memoLabel.textContent = "memo";
  memoInput.id = "travel-experience-memo";
  memoInput.name = "memo";
  memoInput.value = experience.memo || "";
  memoField.appendChild(memoLabel);
  memoField.appendChild(memoInput);

  statusField.className = "travel-experience-edit-field";
  statusLabel.setAttribute("for", "travel-experience-status");
  statusLabel.textContent = "status";
  statusSelect.id = "travel-experience-status";
  statusSelect.name = "status";
  appendExperienceStatusOption(statusSelect, "");
  statusSelect.options[0].textContent = "未定";
  if (status && !experienceStatusIsKnown(status)) {
    appendExperienceStatusOption(statusSelect, status);
  }
  for (index = 0; index < experienceStatusOptions.length; index += 1) {
    appendExperienceStatusOption(statusSelect, experienceStatusOptions[index]);
  }
  statusSelect.value = status;
  statusField.appendChild(statusLabel);
  statusField.appendChild(statusSelect);

  error.className = "travel-error travel-experience-edit-error";
  error.hidden = true;

  actions.className = "travel-experience-edit-actions";
  saveButton.type = "submit";
  saveButton.textContent = "保存";
  cancelButton.type = "button";
  cancelButton.textContent = "キャンセル";
  cancelButton.addEventListener("click", function () {
    cancelExperienceEdit(elements, data);
  });
  actions.appendChild(saveButton);
  actions.appendChild(cancelButton);

  form.appendChild(titleField);
  form.appendChild(memoField);
  form.appendChild(statusField);
  form.appendChild(error);
  form.appendChild(actions);
  form.addEventListener("submit", function (event) {
    submitExperienceUpdate(event, elements, data);
  });

  elements.detailContent.appendChild(form);
  renderExperienceEditError(form, errorText);
  showDetail(elements);
}

function cancelExperienceEdit(elements, data) {
  renderExperienceDetail(elements, data);
}

async function submitExperienceUpdate(event, elements, data) {
  var form = event.target;
  var experienceId = form.getAttribute("data-experience-id");
  var saveButton = form.querySelector('button[type="submit"]');
  var payload;

  event.preventDefault();
  if (!experienceId) {
    renderExperienceEditError(form, "Experience IDが見つかりませんでした。");
    return;
  }

  payload = {
    display_title: form.elements.display_title.value,
    memo: form.elements.memo.value,
  };
  if (form.elements.status.value) {
    payload.status = form.elements.status.value;
  }

  if (saveButton) {
    saveButton.disabled = true;
  }
  setTravelStatus(elements, "Experience保存中", false);

  try {
    await api("/api/travel/experiences/" + encodeURIComponent(experienceId), {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    await loadExperienceDetail(experienceId);
    setTravelStatus(elements, "Experience保存済み", false);
  } catch (error) {
    renderExperienceEditError(form, error.message || "Experienceを保存できませんでした。");
    setTravelStatus(elements, error.message, true);
  } finally {
    if (saveButton) {
      saveButton.disabled = false;
    }
  }
}

function renderExperienceDetail(elements, data) {
  var experience = data.experience || data.spot || {};
  var actions = renderExperienceActions(elements, data);
  var title = document.createElement("h3");
  var type = document.createElement("p");
  var meta = document.createElement("div");
  var memo = document.createElement("p");
  var linkedPhotosSection;
  var photosSection;
  var outOfRangeSection;

  clearNode(elements.detailContent);
  currentTravelView = "experience";
  if (elements.backButton) {
    elements.backButton.textContent = "旅行へ戻る";
  }

  type.className = "travel-experience-type";
  type.textContent = "Experience Type: " + experienceTypeLabel(experience);

  title.className = "travel-detail-title";
  title.textContent = experienceTitle(experience);

  meta.className = "travel-spot-meta-list";
  meta.appendChild(renderSpotMeta("開始日時", normalizeDate(experience.start_at)));
  meta.appendChild(renderSpotMeta("終了日時", normalizeDate(experience.end_at)));
  meta.appendChild(renderSpotMeta("status", experience.status || "未定"));

  memo.className = "travel-spot-memo";
  memo.textContent = experience.memo || "メモはありません";

  linkedPhotosSection = renderExperienceLinkedPhotosSection(elements, data);
  photosSection = renderExperiencePhotosSection(elements, data);
  outOfRangeSection = renderOutOfRangePhotoLinkNotice(elements, data);

  elements.detailContent.appendChild(actions);
  elements.detailContent.appendChild(type);
  elements.detailContent.appendChild(title);
  elements.detailContent.appendChild(meta);
  elements.detailContent.appendChild(linkedPhotosSection);
  elements.detailContent.appendChild(photosSection);
  elements.detailContent.appendChild(outOfRangeSection);
  elements.detailContent.appendChild(memo);
  showDetail(elements);
}

function renderSpotDetail(elements, data) {
  renderExperienceDetail(elements, data);
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

async function loadExperienceDetail(experienceId) {
  var elements = getElements();
  var data;
  var linkData;
  var pagination;

  if (!elements.screen || !elements.detail || !elements.detailContent || detailLoading) {
    return;
  }

  detailLoading = true;
  currentTravelView = "experience";
  if (elements.backButton) {
    elements.backButton.textContent = "旅行へ戻る";
  }
  setTravelStatus(elements, "Experience詳細読み込み中", false);

  try {
    data = await api(
      "/api/travel/experiences/" +
        encodeURIComponent(experienceId) +
        "?limit=" +
        experiencePhotosPageSize +
        "&offset=0"
    );
    data.photoError = data.photo_error || false;
    try {
      linkData = await api(
        "/api/travel/experiences/" +
          encodeURIComponent(experienceId) +
          "/photo-links"
      );
      data.photoLinks = linkData.links || [];
    } catch (linkError) {
      data.photoLinks = [];
    }
    data.experiencePhotosLimit = experiencePhotosPageSize;
    pagination = experiencePhotoPagination(data);
    data.experiencePhotosHasMore = experiencePhotosHasMore(
      data.photos || [],
      pagination,
      experiencePhotosPageSize
    );
    renderExperienceDetail(elements, data);
    setTravelStatus(elements, "Experience詳細取得済み", false);
  } catch (error) {
    if (error.message === "Travel experience not found") {
      renderDetailError(elements, "Experienceが見つかりませんでした。");
    } else {
      renderDetailError(elements, "Experience詳細を取得できませんでした。");
    }
    setTravelStatus(elements, error.message, true);
  } finally {
    detailLoading = false;
  }
}

async function linkExperiencePhoto(elements, data, assetId, linkType) {
  var experienceId = experienceIdFromData(data);
  var response;

  if (!experienceId || !assetId || experiencePhotoLinkLoading) {
    return;
  }

  experiencePhotoLinkLoading = true;
  renderExperienceDetail(elements, data);
  setTravelStatus(elements, "写真リンク保存中", false);

  try {
    response = await api(
      "/api/travel/experiences/" +
        encodeURIComponent(experienceId) +
        "/photo-links",
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          photo_asset_id: assetId,
          link_type: linkType || "linked",
        }),
      }
    );
    mergeExperiencePhotoLink(data, response.link);
    renderExperienceDetail(elements, data);
    setTravelStatus(elements, "写真リンク保存済み", false);
  } catch (error) {
    setTravelStatus(elements, error.message || "写真リンクを保存できませんでした。", true);
  } finally {
    experiencePhotoLinkLoading = false;
    renderExperienceDetail(elements, data);
  }
}

async function loadExperiencePhotosPage(elements, data, offset, limit) {
  var experienceId = experienceIdFromData(data);
  var pageData;

  if (!experienceId || experiencePhotosLoading) {
    return;
  }

  experiencePhotosLoading = true;
  renderExperienceDetail(elements, data);
  setTravelStatus(elements, "Experience写真読み込み中", false);

  try {
    pageData = await api(
      "/api/travel/experiences/" +
        encodeURIComponent(experienceId) +
        "/photos?limit=" +
        limit +
        "&offset=" +
        offset
    );
    appendExperiencePhotos(data, pageData);
    data.photoError = false;
    renderExperienceDetail(elements, data);
    setTravelStatus(elements, "Experience写真取得済み", false);
  } catch (error) {
    setTravelStatus(elements, error.message, true);
  } finally {
    experiencePhotosLoading = false;
    renderExperienceDetail(elements, data);
  }
}

async function loadSpotDetail(spotId) {
  return loadExperienceDetail(spotId);
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
      var nextElements = getElements();
      if (
        (currentTravelView === "experience" ||
          currentTravelView === "spot" ||
          currentTravelView === "experience-create") &&
        currentTripDetailData
      ) {
        renderTravelDetail(nextElements, currentTripDetailData);
        setTravelStatus(nextElements, "詳細取得済み", false);
        return;
      }
      showList(nextElements);
      setTravelStatus(nextElements, "取得済み", false);
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
