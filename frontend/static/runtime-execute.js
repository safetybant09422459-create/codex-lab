var runtimeExecuteElements = {};

function runtimeElement(id) {
  return document.getElementById(id);
}

function setRuntimeStatus(text, isError) {
  var message = runtimeExecuteElements.message;
  if (!message) {
    return;
  }
  message.textContent = text;
  if (message.classList) {
    if (isError) {
      message.classList.add("error");
    } else {
      message.classList.remove("error");
    }
  }
}

function setRuntimePhotoDebug(text, isError) {
  var debug = runtimeExecuteElements.photoDebug;
  var line;

  if (!debug) {
    return null;
  }

  line = document.createElement("div");
  line.className = isError ? "photo-debug-line error" : "photo-debug-line";
  line.textContent = text;
  debug.appendChild(line);
  return line;
}

function resetRuntimePhotoDebug() {
  var debug = runtimeExecuteElements.photoDebug;

  if (!debug) {
    return;
  }

  debug.innerHTML = "";
}

function runtimeErrorMessage(error) {
  if (error && error.message) {
    return error.message;
  }
  return String(error);
}

function showRuntimePhotoError(text) {
  var container = runtimeExecuteElements.photoPreview;

  if (container) {
    container.hidden = false;
  }

  setRuntimePhotoDebug(text, true);
}

function asRuntimeArray(value) {
  return Array.isArray(value) ? value : [];
}

function runtimePhotosHaveThumbnails(photos) {
  var i;

  for (i = 0; i < photos.length; i += 1) {
    if (photos[i] && typeof photos[i] === "object" && photos[i].thumbnail_url) {
      return true;
    }
  }

  return false;
}

function photoItemsFromRuntimeValue(value) {
  var candidates = [];
  var response;
  var responseResult;
  var responseNestedResult;
  var result;
  var nestedResult;
  var i;
  var photos;
  var firstPhotoArray = [];

  if (!value || typeof value !== "object") {
    return [];
  }

  result = value.result && typeof value.result === "object" ? value.result : null;
  nestedResult = result && result.result && typeof result.result === "object" ? result.result : null;
  response = value.response && typeof value.response === "object" ? value.response : null;
  responseResult = response && response.result && typeof response.result === "object" ? response.result : null;
  responseNestedResult = responseResult && responseResult.result && typeof responseResult.result === "object" ? responseResult.result : null;

  candidates.push(value.photos);
  if (result) {
    candidates.push(result.photos);
  }
  if (nestedResult) {
    candidates.push(nestedResult.photos);
  }
  if (response) {
    candidates.push(response.photos);
  }
  if (responseResult) {
    candidates.push(responseResult.photos);
  }
  if (responseNestedResult) {
    candidates.push(responseNestedResult.photos);
  }

  for (i = 0; i < candidates.length; i += 1) {
    photos = asRuntimeArray(candidates[i]);
    if (!firstPhotoArray.length && photos.length) {
      firstPhotoArray = photos;
    }
    if (runtimePhotosHaveThumbnails(photos)) {
      return photos;
    }
  }

  return firstPhotoArray;
}

function flashRuntimeCopyButton(button, text) {
  var originalText;

  if (!button) {
    return;
  }

  originalText = button.textContent;
  button.textContent = text;
  window.setTimeout(function () {
    button.textContent = originalText;
  }, 1200);
}

function fallbackCopyRuntimeText(text) {
  var textarea;
  var copied = false;

  if (!text || !document.execCommand) {
    return false;
  }

  textarea = document.createElement("textarea");
  textarea.value = text;
  textarea.setAttribute("readonly", "readonly");
  textarea.style.position = "fixed";
  textarea.style.left = "-9999px";
  textarea.style.top = "0";
  document.body.appendChild(textarea);
  textarea.focus();
  textarea.select();

  try {
    copied = document.execCommand("copy");
  } catch (error) {
    copied = false;
  }

  document.body.removeChild(textarea);
  return copied;
}

function copyRuntimeText(text, button) {
  var clipboard = window.navigator && window.navigator.clipboard;
  var writeResult;

  if (!text) {
    return;
  }

  if (!clipboard || !clipboard.writeText) {
    if (fallbackCopyRuntimeText(text)) {
      flashRuntimeCopyButton(button, "Copied");
      setRuntimeStatus("asset_id copied with fallback", false);
      return;
    }
    setRuntimeStatus("asset_id copy failed", true);
    return;
  }

  try {
    writeResult = clipboard.writeText(text);
  } catch (error) {
    if (fallbackCopyRuntimeText(text)) {
      flashRuntimeCopyButton(button, "Copied");
      setRuntimeStatus("asset_id copied with fallback", false);
      return;
    }
    setRuntimeStatus("asset_id copy failed", true);
    return;
  }

  if (!writeResult || !writeResult.then) {
    if (fallbackCopyRuntimeText(text)) {
      flashRuntimeCopyButton(button, "Copied");
      setRuntimeStatus("asset_id copied with fallback", false);
      return;
    }
    setRuntimeStatus("asset_id copy failed", true);
    return;
  }

  writeResult.then(function () {
    flashRuntimeCopyButton(button, "Copied");
  }).catch(function () {
    if (fallbackCopyRuntimeText(text)) {
      flashRuntimeCopyButton(button, "Copied");
      setRuntimeStatus("asset_id copied with fallback", false);
      return;
    }
    setRuntimeStatus("asset_id copy failed", true);
  });
}

function createRuntimeCopyButton(assetId) {
  var copyButton = document.createElement("button");

  copyButton.type = "button";
  copyButton.className = "secondary asset-copy";
  copyButton.textContent = assetId;
  copyButton.title = "Copy asset_id: " + assetId;
  copyButton.addEventListener("click", function () {
    try {
      copyRuntimeText(assetId, copyButton);
    } catch (error) {
      console.error("Runtime asset_id copy failed", error);
      setRuntimeStatus("asset_id copy failed", true);
    }
  });

  return copyButton;
}

function showRuntimeImageError(card, text) {
  var errorNode;

  if (!card) {
    return;
  }

  errorNode = document.createElement("div");
  errorNode.className = "photo-image-error";
  errorNode.textContent = text;
  card.appendChild(errorNode);
}

function renderRuntimePhotoPreview(value) {
  var container = runtimeExecuteElements.photoPreview;
  var photos = [];
  var i;
  var photo;
  var card;
  var link;
  var image;
  var meta;
  var assetId;
  var copyButton;
  var takenAt;
  var renderedCount = 0;
  var imageUrl;

  if (!container) {
    setRuntimePhotoDebug("photo preview error: runtime-photo-preview not found", true);
    return;
  }

  container.innerHTML = "";
  try {
    photos = photoItemsFromRuntimeValue(value);
  } catch (error) {
    console.error("Runtime photo extraction failed", error);
    showRuntimePhotoError("photo preview error: " + runtimeErrorMessage(error));
    return;
  }
  setRuntimePhotoDebug("photos found: " + photos.length, false);

  if (!photos.length) {
    container.hidden = true;
    setRuntimePhotoDebug("photo cards rendered: 0", false);
    return;
  }

  container.hidden = false;
  for (i = 0; i < photos.length; i += 1) {
    photo = photos[i];
    if (!photo || typeof photo !== "object" || !photo.thumbnail_url) {
      continue;
    }

    try {
      assetId = photo.asset_id ? String(photo.asset_id) : "";
      imageUrl = String(photo.thumbnail_url);
      card = document.createElement("div");
      card.className = "photo-card";

      link = document.createElement("a");
      link.className = "photo-thumb-link";
      link.href = photo.preview_url || imageUrl;
      link.target = "_blank";
      link.rel = "noopener noreferrer";

      image = document.createElement("img");
      image.alt = assetId ? "Photo " + assetId : "Photo thumbnail";
      image.loading = "lazy";
      image.onerror = (function (targetImage, targetCard) {
        return function () {
          try {
            targetImage.onerror = null;
            showRuntimeImageError(targetCard, "Image load error");
          } catch (error) {
            console.error("Runtime image error display failed", error);
          }
        };
      }(image, card));
      image.src = imageUrl;
      link.appendChild(image);
      card.appendChild(link);

      meta = document.createElement("div");
      meta.className = "photo-meta";

      if (assetId) {
        copyButton = createRuntimeCopyButton(assetId);
        meta.appendChild(copyButton);
      }

      takenAt = document.createElement("span");
      takenAt.textContent = photo.taken_at || photo.source || "";
      meta.appendChild(takenAt);
      card.appendChild(meta);
      container.appendChild(card);
      renderedCount += 1;
    } catch (error) {
      console.error("Runtime photo render failed", error);
      setRuntimePhotoDebug("photo preview error: " + runtimeErrorMessage(error), true);
    }
  }

  if (!renderedCount) {
    setRuntimePhotoDebug("photo cards rendered: 0", false);
    return;
  }

  setRuntimePhotoDebug("photo cards rendered: " + renderedCount, false);
  setRuntimeStatus("Photo preview rendered: " + renderedCount, false);
}

function showRuntimeResult(value) {
  resetRuntimePhotoDebug();
  setRuntimePhotoDebug("showRuntimeResult called", false);
  if (!runtimeExecuteElements.result) {
    return;
  }
  try {
    renderRuntimePhotoPreview(value);
  } catch (error) {
    console.error("Runtime photo preview failed", error);
    showRuntimePhotoError("photo preview error: " + runtimeErrorMessage(error));
    setRuntimeStatus("Photo preview failed; JSON result is still shown", true);
  }
  if (typeof value === "string") {
    runtimeExecuteElements.result.textContent = value;
    return;
  }
  runtimeExecuteElements.result.textContent = JSON.stringify(value, null, 2);
}

function showRuntimeAudit(value) {
  if (!runtimeExecuteElements.audit) {
    return;
  }
  if (typeof value === "string") {
    runtimeExecuteElements.audit.textContent = value;
    return;
  }
  runtimeExecuteElements.audit.textContent = JSON.stringify(value, null, 2);
}

function parseRuntimeJson() {
  var text = runtimeExecuteElements.params.value.trim();
  var parsed;
  if (!text) {
    return {};
  }
  parsed = JSON.parse(text);
  if (!parsed || Array.isArray(parsed) || typeof parsed !== "object") {
    throw new Error("Params JSON must be an object.");
  }
  return parsed;
}

function fetchRuntimeJson(path, options) {
  return fetch(path, options).then(function (response) {
    return response.json().catch(function () {
      return {};
    }).then(function (data) {
      if (!response.ok) {
        throw new Error(data.detail || "HTTP " + response.status);
      }
      return data;
    });
  });
}

function normalizeRuntimeTools(data) {
  var rawTools = null;
  var tools = [];
  var i;
  var rawTool;
  var toolId;
  var skillId;

  if (Array.isArray(data)) {
    rawTools = data;
  } else if (data && Array.isArray(data.tools)) {
    rawTools = data.tools;
  } else if (data && Array.isArray(data.data)) {
    rawTools = data.data;
  } else if (data && data.data && Array.isArray(data.data.tools)) {
    rawTools = data.data.tools;
  }

  if (!rawTools) {
    throw new Error("Runtime tools response is invalid.");
  }

  for (i = 0; i < rawTools.length; i += 1) {
    rawTool = rawTools[i];
    if (!rawTool || typeof rawTool !== "object") {
      continue;
    }
    toolId = rawTool.id || rawTool.tool_id || rawTool.name;
    if (!toolId) {
      continue;
    }
    skillId = rawTool.skill_id || rawTool.skill || "";
    tools.push({
      id: String(toolId),
      skill_id: String(skillId),
    });
  }

  return tools;
}

function renderRuntimeTools(tools) {
  var select = runtimeExecuteElements.toolSelect;
  var preferredIndex = -1;
  var i;
  var tool;
  var option;

  if (!select) {
    setRuntimeStatus("Runtime tool select not found", true);
    return 0;
  }

  select.innerHTML = "";
  for (i = 0; i < tools.length; i += 1) {
    tool = tools[i];
    option = document.createElement("option");
    option.value = tool.id;
    option.textContent = tool.skill_id ? tool.id + " (" + tool.skill_id + ")" : tool.id;
    select.appendChild(option);
    if (tool.id === "get_forecast") {
      preferredIndex = i;
    }
  }

  if (preferredIndex >= 0) {
    select.selectedIndex = preferredIndex;
  }

  return tools.length;
}

export function loadRuntimeTools() {
  if (!runtimeExecuteElements.toolSelect) {
    setRuntimeStatus("Runtime tool select not found", true);
    return Promise.resolve();
  }

  setRuntimeStatus("Runtime tools 読み込み中...", false);
  return fetchRuntimeJson("/api/tools").then(function (data) {
    var tools = normalizeRuntimeTools(data);
    var count = renderRuntimeTools(tools);
    setRuntimeStatus("Runtime tools loaded: " + count, false);
  }).catch(function (error) {
    if (runtimeExecuteElements.toolSelect) {
      runtimeExecuteElements.toolSelect.innerHTML = "";
    }
    setRuntimeStatus("Runtime tools error: " + error.message, true);
    showRuntimeResult("Runtime tools error: " + error.message);
  });
}

export function executeRuntimeTool() {
  var toolId;
  var params;
  var payload;

  if (!runtimeExecuteElements.toolSelect) {
    return Promise.resolve();
  }

  toolId = runtimeExecuteElements.toolSelect.value;
  if (!toolId) {
    showRuntimeResult("Runtime Execute error: tool is not selected.");
    return Promise.resolve();
  }

  try {
    params = parseRuntimeJson();
  } catch (error) {
    showRuntimeResult("Params JSON error: " + error.message);
    return Promise.resolve();
  }

  payload = {
    tool_id: toolId,
    params: params,
    role: runtimeExecuteElements.roleSelect.value,
    confirmed: runtimeExecuteElements.confirmed.checked,
  };

  runtimeExecuteElements.executeButton.disabled = true;
  showRuntimeResult("Executing...");

  return fetchRuntimeJson("/api/runtime/execute", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  }).then(function (data) {
    showRuntimeResult(data);
    return refreshRuntimeAudit();
  }).catch(function (error) {
    showRuntimeResult("Runtime Execute error: " + error.message);
  }).then(function () {
    runtimeExecuteElements.executeButton.disabled = false;
  });
}

export function refreshRuntimeAudit() {
  return fetchRuntimeJson("/api/audit?limit=20").then(function (data) {
    showRuntimeAudit(data);
  }).catch(function (error) {
    showRuntimeAudit("Runtime audit error: " + error.message);
  });
}

export function initRuntimeExecute() {
  runtimeExecuteElements = {
    toolSelect: runtimeElement("runtime-tool-select"),
    roleSelect: runtimeElement("runtime-role-select"),
    confirmed: runtimeElement("runtime-confirmed"),
    params: runtimeElement("runtime-params-json"),
    executeButton: runtimeElement("runtime-execute-button"),
    result: runtimeElement("runtime-result"),
    photoPreview: runtimeElement("runtime-photo-preview"),
    photoDebug: runtimeElement("runtime-photo-debug"),
    auditButton: runtimeElement("runtime-audit-refresh-button"),
    audit: runtimeElement("runtime-audit"),
    message: runtimeElement("runtime-execute-message"),
  };

  if (!runtimeExecuteElements.toolSelect) {
    setRuntimeStatus("Runtime tool select not found", true);
    return;
  }

  if (!runtimeExecuteElements.executeButton) {
    return;
  }

  runtimeExecuteElements.executeButton.addEventListener("click", function () {
    try {
      executeRuntimeTool();
    } catch (error) {
      showRuntimeResult("Runtime Execute error: " + runtimeErrorMessage(error));
    }
  });
  if (runtimeExecuteElements.auditButton) {
    runtimeExecuteElements.auditButton.addEventListener("click", function () {
      try {
        refreshRuntimeAudit();
      } catch (error) {
        showRuntimeAudit("Runtime audit error: " + runtimeErrorMessage(error));
      }
    });
  }

  loadRuntimeTools();
  refreshRuntimeAudit();
}
