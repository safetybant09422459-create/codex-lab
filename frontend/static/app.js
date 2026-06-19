import { bindTabs } from "./tabs.js";
import { bindGitActions, loadProject, refreshChanges } from "./review.js";
import { bindServiceActions, refreshService, refreshSkills, refreshTools } from "./update.js";
import { api } from "./api.js";
import { refreshLogs } from "./logs.js";
import { initRuntimeExecute } from "./runtime-execute.js";
import { elements, runtime, setStatus, setTopState } from "./state.js";

function bindDevelopActions() {
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
initRuntimeExecute();

const initialLoads = [
  ["project", loadProject],
  ["logs", refreshLogs],
  ["changes", refreshChanges],
  ["skills", refreshSkills],
  ["tools", refreshTools],
  ["service", refreshService],
];

Promise.allSettled(initialLoads.map(([, load]) => load())).then((results) => {
  const failures = results
    .map((result, index) => ({ result, name: initialLoads[index][0] }))
    .filter(({ result }) => result.status === "rejected");

  if (!failures.length) {
    return;
  }

  console.error(
    "Initial load failed",
    failures.map(({ name, result }) => ({
      name,
      error: result.reason,
    })),
  );
  setStatus(
    elements.runStatus,
    `初期読み込み失敗: ${failures.map(({ name }) => name).join(", ")}`,
    true,
  );
});
