export const elements = {
  projectName: document.querySelector("#project-name"),
  projectPath: document.querySelector("#project-path"),
  projectBranch: document.querySelector("#project-branch"),
  projectGit: document.querySelector("#project-git"),
  stateValue: document.querySelector("#state-value"),
  codexPrompt: document.querySelector("#codex-prompt"),
  sendCodexButton: document.querySelector("#send-codex-button"),
  newCodexSessionButton: document.querySelector("#new-codex-session-button"),
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
  commitPushButton: document.querySelector("#commit-push-button"),
  preflightFailure: document.querySelector("#preflight-failure"),
  preflightBlockers: document.querySelector("#preflight-blockers"),
  preflightFindings: document.querySelector("#preflight-findings"),
  preflightOpenDiff: document.querySelector("#preflight-open-diff"),
  preflightIgnoreOnce: document.querySelector("#preflight-ignore-once"),
  preflightCancel: document.querySelector("#preflight-cancel"),
  skillsList: document.querySelector("#skills-list"),
  skillsMessage: document.querySelector("#skills-message"),
  toolsList: document.querySelector("#tools-list"),
  toolsMessage: document.querySelector("#tools-message"),
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
