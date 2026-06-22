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
  message.classList.toggle("error", Boolean(isError));
}

function asRuntimeArray(value) {
  return Array.isArray(value) ? value : [];
}

function photoItemsFromRuntimeValue(value) {
  var result = value && typeof value === "object" ? value.result : null;

  if (result && typeof result === "object") {
    return asRuntimeArray(result.photos);
  }
  if (value && typeof value === "object") {
    return asRuntimeArray(value.photos);
  }
  return [];
}

function copyRuntimeText(text, button) {
  if (!text || !navigator.clipboard) {
    return;
  }
  navigator.clipboard.writeText(text).then(function () {
    var originalText = button.textContent;
    button.textContent = "Copied";
    window.setTimeout(function () {
      button.textContent = originalText;
    }, 1200);
  }).catch(function () {
    setRuntimeStatus("asset_id copy failed", true);
  });
}

function renderRuntimePhotoPreview(value) {
  var container = runtimeExecuteElements.photoPreview;
  var photos = photoItemsFromRuntimeValue(value);
  var i;
  var photo;
  var card;
  var link;
  var image;
  var meta;
  var assetId;
  var copyButton;
  var takenAt;

  if (!container) {
    return;
  }

  container.innerHTML = "";
  if (!photos.length) {
    container.hidden = true;
    return;
  }

  container.hidden = false;
  for (i = 0; i < photos.length; i += 1) {
    photo = photos[i];
    if (!photo || typeof photo !== "object" || !photo.thumbnail_url) {
      continue;
    }

    assetId = photo.asset_id ? String(photo.asset_id) : "";
    card = document.createElement("div");
    card.className = "photo-card";

    link = document.createElement("a");
    link.className = "photo-thumb-link";
    link.href = photo.preview_url || photo.thumbnail_url;
    link.target = "_blank";
    link.rel = "noopener noreferrer";

    image = document.createElement("img");
    image.src = photo.thumbnail_url;
    image.alt = assetId ? "Photo " + assetId : "Photo thumbnail";
    image.loading = "lazy";
    link.appendChild(image);
    card.appendChild(link);

    meta = document.createElement("div");
    meta.className = "photo-meta";

    if (assetId) {
      copyButton = document.createElement("button");
      copyButton.type = "button";
      copyButton.className = "secondary asset-copy";
      copyButton.textContent = assetId;
      copyButton.title = "Copy asset_id";
      copyButton.addEventListener("click", copyRuntimeText.bind(null, assetId, copyButton));
      meta.appendChild(copyButton);
    }

    takenAt = document.createElement("span");
    takenAt.textContent = photo.taken_at || photo.source || "";
    meta.appendChild(takenAt);
    card.appendChild(meta);
    container.appendChild(card);
  }

  if (!container.children.length) {
    container.hidden = true;
  }
}

function showRuntimeResult(value) {
  if (!runtimeExecuteElements.result) {
    return;
  }
  renderRuntimePhotoPreview(value);
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

  runtimeExecuteElements.executeButton.addEventListener("click", executeRuntimeTool);
  runtimeExecuteElements.auditButton.addEventListener("click", refreshRuntimeAudit);

  loadRuntimeTools();
  refreshRuntimeAudit();
}
