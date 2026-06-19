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

function showRuntimeResult(value) {
  if (!runtimeExecuteElements.result) {
    return;
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
