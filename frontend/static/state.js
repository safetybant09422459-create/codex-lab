export const elements = {
  projectName: document.querySelector("#project-name"),
  projectPath: document.querySelector("#project-path"),
  projectBranch: document.querySelector("#project-branch"),
  projectGit: document.querySelector("#project-git"),
  stateValue: document.querySelector("#state-value"),
  designInput: document.querySelector("#design-input"),
  codexPrompt: document.querySelector("#codex-prompt"),
  regeneratePromptButton: document.querySelector("#regenerate-prompt-button"),
  sendCodexButton: document.querySelector("#send-codex-button"),
  runStatus: document.querySelector("#run-status"),
  tokens: document.querySelector("#tokens"),
  finalAnswer: document.querySelector("#final-answer"),
  log: document.querySelector("#log"),
  returnCode: document.querySelector("#return-code"),
  fileCount: document.querySelector("#file-count"),
  fileList: document.querySelector("#file-list"),
  gitStatus: document.querySelector("#git-status"),
  diffList: document.querySelector("#diff-list"),
  gitMessage: document.querySelector("#git-message"),
  commitMessage: document.querySelector("#commit-message"),
  commitButton: document.querySelector("#commit-button"),
  pushButton: document.querySelector("#push-button"),
  serviceStatus: document.querySelector("#service-status"),
  serviceMessage: document.querySelector("#service-message"),
  serviceRefreshButton: document.querySelector("#service-refresh-button"),
  serviceRestartButton: document.querySelector("#service-restart-button"),
};

export const runtime = {
  polling: null,
  project: {
    name: "Jarvis Developer",
    local_path: "/mnt/nas/projects/codex-lab",
    branch: "main",
    git_state: "unknown",
  },
};

export const stateLabels = {
  idle: "待機中",
  running: "実行中",
  succeeded: "完了",
  failed: "失敗",
};

export const statusLabels = {
  new: "新規",
  modified: "変更",
  deleted: "削除",
};

export function escapeHtml(value) {
  return String(value).replace(/[&<>"']/g, (char) => ({
    "&": "&amp;",
    "<": "&lt;",
    ">": "&gt;",
    "\"": "&quot;",
    "'": "&#39;",
  })[char]);
}

export function setStatus(element, text, isError = false) {
  element.textContent = text;
  element.classList.toggle("error", isError);
}

export function setTopState(state) {
  elements.stateValue.textContent = stateLabels[state] || "待機中";
  elements.stateValue.className = `state-value ${state || "idle"}`;
}

export function generatePrompt() {
  const design = elements.designInput.value.trim();
  return `Project名: ${runtime.project.name}
Local Path: ${runtime.project.local_path}
Branch: ${runtime.project.branch}

設計内容:
${design || "未入力"}

必須ルール:
- git commit / git push を実行しないこと
- /mnt/nas/projects/project を触らないこと
- 破壊的操作をしないこと
- 変更は設計内容と許可ファイルの範囲に限定すること
- 完了後は、変更ファイル一覧、変更した画面、動作確認手順、未実装事項、git commit / git push は実行していないことだけを最終回答に含めること`;
}
