import { bindTabs } from "./tabs.js";
import { bindGitActions, loadProject, refreshChanges } from "./review.js";
import { bindServiceActions } from "./update.js";
import { api } from "./api.js";
import { refreshLogs } from "./logs.js";
import { elements, generatePrompt, runtime, setStatus, setTopState } from "./state.js";

function bindDevelopActions() {
  elements.designInput.addEventListener("input", () => {
    elements.codexPrompt.value = generatePrompt();
    setStatus(elements.runStatus, "送信内容を自動生成済み");
  });

  elements.regeneratePromptButton.addEventListener("click", () => {
    elements.codexPrompt.value = generatePrompt();
    setStatus(elements.runStatus, "再生成済み");
  });

  elements.sendCodexButton.addEventListener("click", async () => {
    const prompt = elements.codexPrompt.value.trim();
    if (!prompt) {
      setStatus(elements.runStatus, "送信内容を入力してください", true);
      return;
    }
    if (!confirm("表示中の内容をCodexへ送信します。続行しますか？")) {
      return;
    }

    elements.sendCodexButton.disabled = true;
    elements.returnCode.textContent = "";
    elements.tokens.textContent = "tokens used: -";
    elements.finalAnswer.textContent = "最終回答を待っています...";
    elements.log.textContent = "起動中...";
    setTopState("running");
    setStatus(elements.runStatus, "起動中");

    try {
      await api("/api/run", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ prompt }),
      });
      await refreshLogs();
      runtime.polling = setInterval(refreshLogs, 1000);
    } catch (error) {
      elements.sendCodexButton.disabled = false;
      setStatus(elements.runStatus, error.message, true);
    }
  });
}

bindTabs();
bindDevelopActions();
bindGitActions();
bindServiceActions();

Promise.all([loadProject(), refreshLogs(), refreshChanges()])
  .catch((error) => setStatus(elements.runStatus, error.message, true));
