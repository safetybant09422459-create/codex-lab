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
  let failedPreflight = null;

  function closePreflightFailure() {
    failedPreflight = null;
    elements.preflightFailure.hidden = true;
  }

  function showPreflightFailure(preflight) {
    failedPreflight = preflight;
    elements.preflightBlockers.innerHTML = preflight.blockers.map((blocker) =>
      `<p>${escapeHtml(blocker)}</p>`
    ).join("");
    elements.preflightFindings.innerHTML = preflight.findings.map((finding) => `
      <article class="preflight-finding">
        <dl>
          <dt>Result</dt><dd>${escapeHtml(finding.disposition)}</dd>
          <dt>Failed rule</dt><dd>${escapeHtml(finding.rule)}</dd>
          <dt>File</dt><dd>${escapeHtml(finding.file)}</dd>
          <dt>Line</dt><dd>${finding.line}</dd>
          <dt>Detected</dt><dd><code>${escapeHtml(finding.detected_text)}</code></dd>
          <dt>How to fix</dt><dd>${escapeHtml(finding.remediation)}</dd>
        </dl>
      </article>
    `).join("");
    elements.preflightIgnoreOnce.hidden = !preflight.findings.length
      || preflight.findings.some((finding) => !finding.ignorable)
      || preflight.blockers.some((blocker) =>
        blocker !== "A possible secret was detected in the diff."
      );
    elements.preflightFailure.hidden = false;
  }

  async function commitPush(preflight, ignoredFindingIds) {
    const data = await api("/api/git/commit_push", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        confirm: true,
        expected_snapshot: preflight.snapshot,
        ignored_finding_ids: ignoredFindingIds,
      }),
    });
    closePreflightFailure();
    setStatus(elements.gitMessage, `成功: ${data.commit_hash}\n${data.push_output}`);
    await refreshChanges();
    await loadProject();
  }

  elements.preflightCancel.addEventListener("click", closePreflightFailure);
  elements.preflightOpenDiff.addEventListener("click", () => {
    if (!failedPreflight || !failedPreflight.findings.length) return;
    const path = failedPreflight.findings[0].file;
    const pre = Array.from(elements.diffList.querySelectorAll("[data-diff-path]"))
      .find((item) => item.dataset.diffPath === path);
    if (!pre) return;
    const details = pre.closest("details");
    if (details) details.open = true;
    pre.scrollIntoView({ behavior: "smooth", block: "center" });
  });
  elements.preflightIgnoreOnce.addEventListener("click", async () => {
    if (!failedPreflight) return;
    const approved = confirm(
      "Secret検出を今回だけ無視してcommit / pushします。内容をDiffで確認済みですか？"
    );
    if (!approved) return;
    try {
      await commitPush(
        failedPreflight,
        failedPreflight.findings.map((finding) => finding.id)
      );
    } catch (error) {
      setStatus(elements.gitMessage, error.message, true);
    }
  });

  elements.commitPushButton.addEventListener("click", async () => {
    try {
      setStatus(elements.gitMessage, "安全チェックを実行中...");
      const preflight = await api("/api/git/preflight");
      if (!preflight.ok) {
        showPreflightFailure(preflight);
        setStatus(elements.gitMessage, "Preflight failed", true);
        return;
      }
      const approved = confirm(
        `以下をcommitして ${preflight.upstream} へpushします。\n\n`
        + `${preflight.commit_message}\n\n${preflight.summary}\n\n`
        + `${preflight.files.join("\n")}\n\n続行しますか？`
      );
      if (!approved) return;
      await commitPush(preflight, []);
    } catch (error) {
      setStatus(elements.gitMessage, error.message, true);
    }
  });
}
