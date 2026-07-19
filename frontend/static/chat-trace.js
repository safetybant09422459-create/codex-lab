import { api } from "./api.js";

let initialized = false;
let traces = [];
let selectedId = null;
let selectedTrace = null;

function el(id) { return document.getElementById(id); }

function setMessage(message, error) {
  const target = el("chat-trace-message");
  target.textContent = message || "";
  target.classList.toggle("error", Boolean(error));
}

function formatToken(value) {
  return typeof value === "number" ? String(value) : "未取得";
}

function renderList() {
  const list = el("chat-trace-list");
  list.textContent = "";
  el("chat-trace-count").textContent = `${traces.length}件`;
  if (!traces.length) {
    const empty = document.createElement("p");
    empty.className = "muted";
    empty.textContent = "保存中のChat Traceはありません。";
    list.appendChild(empty);
    return;
  }
  traces.forEach((trace) => {
    const button = document.createElement("button");
    button.type = "button";
    button.className = "chat-trace-item" + (trace.turn_id === selectedId ? " selected" : "");
    const title = document.createElement("strong");
    title.textContent = trace.user_input_preview || "（入力なし）";
    const meta = document.createElement("span");
    meta.textContent = `${trace.created_at || "-"} · ${trace.overall_status || "-"} · ${trace.model || "-"} · tokens ${formatToken(trace.total_tokens)} · ${trace.total_duration_ms == null ? "-" : trace.total_duration_ms + "ms"}`;
    button.appendChild(title);
    button.appendChild(meta);
    button.addEventListener("click", () => loadDetail(trace.turn_id));
    list.appendChild(button);
  });
}

function renderDetail(trace) {
  const stages = trace.stages || {};
  const anomaly = (trace.anomaly_flags || [])[0] || null;
  el("chat-trace-summary").textContent = JSON.stringify({
    overall_status: trace.overall_status,
    primary_suspect: anomaly ? { stage: anomaly.stage, reason: anomaly.message } : "異常候補なし",
    anomaly_flags: trace.anomaly_flags || [],
    pipeline: Object.keys(stages).map((name) => ({ name, status: stages[name].status, duration_ms: stages[name].duration_ms })),
  }, null, 2);
  el("chat-trace-detail-json").textContent = JSON.stringify({
    llm_call_1: (trace.llm_calls || [])[0] || null,
    action_1: stages.action_validation_1 || null,
    runtime: stages.runtime_execution || null,
    observation: stages.observation_build || null,
    llm_call_2: (trace.llm_calls || [])[1] || null,
    final_action: stages.action_validation_2 || null,
    final_answer: trace.final_answer,
  }, null, 2);
  const usage = trace.token_usage || {};
  el("chat-trace-metrics").textContent = JSON.stringify({
    calls: (trace.llm_calls || []).map((call) => ({
      step: call.step,
      input: formatToken(call.usage && call.usage.input_tokens),
      cached: formatToken(call.usage && call.usage.cached_input_tokens),
      output: formatToken(call.usage && call.usage.output_tokens),
      reasoning: formatToken(call.usage && call.usage.reasoning_tokens),
      total: formatToken(call.usage && call.usage.total_tokens),
    })),
    turn_total: {
      input: formatToken(usage.input_tokens_total), cached: formatToken(usage.cached_input_tokens_total),
      output: formatToken(usage.output_tokens_total), reasoning: formatToken(usage.reasoning_tokens_total),
      total: formatToken(usage.total_tokens),
    },
    total_duration_ms: trace.total_duration_ms,
    error_category: trace.error_category,
    error_message: trace.error_message,
  }, null, 2);
  ["chat-trace-copy-consultation", "chat-trace-copy-full", "chat-trace-copy-json"].forEach((id) => { el(id).disabled = false; });
}

async function loadDetail(turnId) {
  try {
    selectedTrace = await api(`/api/developer/chat-traces/${encodeURIComponent(turnId)}`);
    selectedId = turnId;
    renderList();
    renderDetail(selectedTrace);
    setMessage("Trace詳細を読み込みました。", false);
  } catch (error) {
    setMessage(`Trace詳細の読み込みに失敗: ${error.message}`, true);
  }
}

export async function refreshChatTraces() {
  try {
    const previous = selectedId;
    traces = await api("/api/developer/chat-traces?limit=50");
    renderList();
    const retained = traces.some((trace) => trace.turn_id === previous);
    if (retained) {
      await loadDetail(previous);
    } else if (traces.length) {
      await loadDetail(traces[0].turn_id);
    } else {
      selectedId = null;
      selectedTrace = null;
      ["chat-trace-copy-consultation", "chat-trace-copy-full", "chat-trace-copy-json"].forEach((id) => { el(id).disabled = true; });
      setMessage("Chat Traceは0件です。", false);
    }
  } catch (error) {
    setMessage(`Trace一覧の読み込みに失敗: ${error.message}`, true);
  }
}

async function fetchBundle(mode) {
  const response = await fetch(`/api/developer/chat-traces/${encodeURIComponent(selectedId)}/bundle?mode=${mode}`);
  if (!response.ok) { throw new Error(`HTTP ${response.status}`); }
  return response.text();
}

export async function copyText(text) {
  if (navigator.clipboard && navigator.clipboard.writeText) {
    try { await navigator.clipboard.writeText(text); return true; } catch (_error) { /* Safari fallback */ }
  }
  const area = document.createElement("textarea");
  area.value = text;
  area.setAttribute("readonly", "");
  area.style.position = "fixed";
  area.style.opacity = "0";
  document.body.appendChild(area);
  area.select();
  area.setSelectionRange(0, area.value.length);
  let copied = false;
  try { copied = document.execCommand("copy"); } finally { document.body.removeChild(area); }
  if (!copied) { throw new Error("clipboard unavailable"); }
  return true;
}

async function copyBundle(mode) {
  if (!selectedId) { return; }
  try {
    await copyText(await fetchBundle(mode));
    setMessage(mode === "full" ? "完全トレースをコピーしました。" : "相談用Bundleをコピーしました。", false);
  } catch (error) { setMessage(`コピーに失敗: ${error.message}`, true); }
}

export function initChatTrace() {
  if (initialized) { return; }
  initialized = true;
  el("chat-trace-refresh").addEventListener("click", refreshChatTraces);
  el("chat-trace-clear").addEventListener("click", async () => {
    if (!confirm("メモリ上の全Chat Traceを消去します。続行しますか？")) { return; }
    try {
      const result = await api("/api/developer/chat-traces", { method: "DELETE" });
      selectedId = null; selectedTrace = null;
      setMessage(`${result.deleted_count}件を消去しました。`, false);
      await refreshChatTraces();
    } catch (error) { setMessage(`消去に失敗: ${error.message}`, true); }
  });
  el("chat-trace-copy-consultation").addEventListener("click", () => copyBundle("consultation"));
  el("chat-trace-copy-full").addEventListener("click", () => copyBundle("full"));
  el("chat-trace-copy-json").addEventListener("click", async () => {
    if (!selectedTrace) { return; }
    try { await copyText(JSON.stringify(selectedTrace, null, 2)); setMessage("JSONをコピーしました。", false); }
    catch (error) { setMessage(`コピーに失敗: ${error.message}`, true); }
  });
}
