import { api } from "./api.js";
import { elements, escapeHtml, setStatus, statusLabels, runtime } from "./state.js";

export async function loadProject() {
  runtime.project = await api("/api/project");
  elements.projectName.textContent = runtime.project.name;
  elements.projectPath.textContent = runtime.project.local_path;
  elements.projectBranch.textContent = runtime.project.branch;
  elements.projectGit.textContent = runtime.project.git_state;
}

export async function refreshChanges() {
  const data = await api("/api/changes");
  elements.fileCount.textContent = `${data.files.length} files`;
  elements.gitStatus.textContent = data.status_text || "変更なし";

  if (!data.files.length) {
    elements.fileList.textContent = "変更ファイルはありません。";
    elements.diffList.textContent = "差分はありません。";
    return;
  }

  elements.fileList.innerHTML = data.files.map((file) => `
    <div class="file-row">
      <span class="badge ${file.status}">${statusLabels[file.status]}</span>
      <span class="file-path">${escapeHtml(file.path)}</span>
    </div>
  `).join("");

  elements.diffList.innerHTML = data.files.map((file) => `
    <details>
      <summary>
        <span>${escapeHtml(file.path)}</span>
        <span class="badge ${file.status}">${statusLabels[file.status]}</span>
      </summary>
      <div>
        <pre class="diff-pre" data-diff-path="${escapeHtml(file.path)}">差分を読み込み中...</pre>
      </div>
    </details>
  `).join("");

  await Promise.all(data.files.map(async (file) => {
    const pre = Array.from(elements.diffList.querySelectorAll("[data-diff-path]"))
      .find((item) => item.dataset.diffPath === file.path);
    if (!pre) return;
    try {
      const diff = await api(`/api/diff?path=${encodeURIComponent(file.path)}`);
      pre.textContent = diff.diff || "差分なし";
    } catch (error) {
      pre.textContent = error.message;
    }
  }));
}

export function bindGitActions() {
  elements.commitButton.addEventListener("click", async () => {
    const message = elements.commitMessage.value.trim();
    if (!message) {
      setStatus(elements.gitMessage, "コミットメッセージを入力してください", true);
      return;
    }
    try {
      const data = await api("/api/commit", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ message }),
      });
      setStatus(elements.gitMessage, data.output || "Committed");
      await refreshChanges();
      await loadProject();
    } catch (error) {
      setStatus(elements.gitMessage, error.message, true);
    }
  });

  elements.pushButton.addEventListener("click", async () => {
    if (!confirm("git push を実行します。続行しますか？")) {
      return;
    }
    const typed = prompt("二重確認: PUSH と入力してください");
    try {
      const data = await api("/api/push", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ confirm: true, confirm_text: typed || "" }),
      });
      setStatus(elements.gitMessage, data.output || "Pushed");
      await refreshChanges();
      await loadProject();
    } catch (error) {
      setStatus(elements.gitMessage, error.message, true);
    }
  });
}
