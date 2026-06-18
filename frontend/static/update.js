import { api } from "./api.js";
import { elements, escapeHtml, setStatus } from "./state.js";

let servicePolling = null;
let restartMessageUntil = 0;

export async function refreshSkills() {
  const skills = await api("/api/skills");
  elements.skillsList.innerHTML = skills.map((skill) => `
    <div class="skill-row">
      <div>
        <strong>${escapeHtml(skill.name)}</strong>
        <p>${escapeHtml(skill.description)}</p>
      </div>
      <div class="skill-meta">
        <span class="pill">${escapeHtml(skill.status)}</span>
        <span class="pill">${escapeHtml(skill.type)}</span>
        <span class="pill">${escapeHtml(skill.mode)}</span>
        <span class="pill">${escapeHtml(skill.risk_level)}</span>
      </div>
    </div>
  `).join("") || "Skillは登録されていません。";
  setStatus(elements.skillsMessage, `${skills.length} skills`);
}

export async function refreshTools() {
  const tools = await api("/api/tools");
  elements.toolsList.innerHTML = tools.map((tool) => `
    <div class="tool-row">
      <strong>${escapeHtml(tool.name)}</strong>
      <span>${escapeHtml(tool.skill_id)}</span>
      <span class="pill">${escapeHtml(tool.mode)}</span>
      <span class="pill">${escapeHtml(tool.risk_level)}</span>
      <span class="pill">${escapeHtml(tool.status)}</span>
    </div>
  `).join("") || "Toolは登録されていません。";
  setStatus(elements.toolsMessage, `${tools.length} tools`);
}

export async function refreshService() {
  try {
    const data = await api("/api/service/status");
    elements.serviceStatus.textContent = formatServiceOutput(data, "status output is empty");
    if (Date.now() >= restartMessageUntil) {
      setStatus(elements.serviceMessage, data.ok ? "running" : "ok=false 取得失敗", !data.ok);
    }
  } catch (error) {
    setStatus(elements.serviceMessage, error.message, true);
  }
}

function formatServiceOutput(data, fallback) {
  const lines = [];
  if (data.command) {
    lines.push(`command:\n${data.command}`);
  }
  if (data.returncode !== undefined && data.returncode !== null) {
    lines.push(`return code:\n${data.returncode}`);
  }
  if (data.output) {
    lines.push(`output:\n${data.output}`);
  }
  if (data.stderr) {
    lines.push(`stderr:\n${data.stderr}`);
  }
  if (!data.ok) {
    lines.unshift("ok=false");
  }
  return lines.join("\n\n") || fallback;
}

export function bindServiceActions() {
  elements.serviceRefreshButton.addEventListener("click", refreshService);
  elements.serviceRestartButton.addEventListener("click", async () => {
    if (!confirm("jarvis-dev を再起動します。続行しますか？")) {
      return;
    }
    try {
      const data = await api("/api/service/restart", { method: "POST" });
      elements.serviceStatus.textContent = formatServiceOutput(data, "restart command completed");
      restartMessageUntil = data.ok ? Date.now() + 2500 : 0;
      setStatus(elements.serviceMessage, data.ok ? "再起動要求を送信しました" : "ok=false 再起動要求失敗", !data.ok);
    } catch (error) {
      setStatus(elements.serviceMessage, error.message, true);
    }
  });

  startServicePolling();
}

export function startServicePolling() {
  if (servicePolling) {
    return;
  }
  refreshService();
  servicePolling = setInterval(refreshService, 3000);
}
