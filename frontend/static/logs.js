import { api } from "./api.js";
import { loadProject, refreshChanges } from "./review.js";
import { elements, runtime, setStatus, setTopState } from "./state.js";

export async function refreshLogs() {
  const data = await api("/api/logs");
  setTopState(data.status);
  elements.finalAnswer.textContent =
    data.final_answer || (data.running ? "最終回答を待っています..." : "最終回答はまだありません。");
  elements.tokens.textContent = `tokens used: ${data.tokens_used || "-"}`;
  elements.log.textContent = data.lines.length ? data.lines.join("\n") : "ログ待機中...";
  elements.returnCode.textContent = data.returncode === null ? "" : `exit ${data.returncode}`;
  elements.log.scrollTop = elements.log.scrollHeight;

  if (!data.running) {
    elements.sendCodexButton.disabled = false;
    clearInterval(runtime.polling);
    runtime.polling = null;
    await refreshChanges();
    await loadProject();
    if (data.returncode === 0) {
      setStatus(elements.runStatus, "完了");
    } else if (data.returncode === null) {
      setStatus(elements.runStatus, "未送信");
    } else {
      setStatus(elements.runStatus, "失敗", true);
    }
  } else {
    setStatus(elements.runStatus, "実行中");
  }
}
