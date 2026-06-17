import { api } from "./api.js";
import { elements, setStatus } from "./state.js";

export async function refreshService() {
  const data = await api("/api/service/status");
  elements.serviceStatus.textContent = data.output || "status output is empty";
  setStatus(elements.serviceMessage, data.ok ? "起動状態を取得" : "取得失敗", !data.ok);
}

export function bindServiceActions() {
  elements.serviceRefreshButton.addEventListener("click", refreshService);
  elements.serviceRestartButton.addEventListener("click", async () => {
    if (!confirm("jarvis-dev を再起動します。続行しますか？")) {
      return;
    }
    try {
      const data = await api("/api/service/restart", { method: "POST" });
      elements.serviceStatus.textContent = data.output || "restart command completed";
      setStatus(elements.serviceMessage, data.ok ? "再起動しました" : "再起動失敗", !data.ok);
    } catch (error) {
      setStatus(elements.serviceMessage, error.message, true);
    }
  });
}
