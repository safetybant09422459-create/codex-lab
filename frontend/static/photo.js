import { api } from "./api.js";

var loaded = false;
var loading = false;

function elements() {
  return {
    screen: document.querySelector("#photo-screen"),
    refresh: document.querySelector("#photo-refresh-button"),
    days: document.querySelector("#photo-days"),
    status: document.querySelector("#photo-status"),
    summary: document.querySelector("#photo-summary"),
    limitations: document.querySelector("#photo-limitations"),
  };
}

function formatDate(value) {
  if (!value) return "記録なし";
  var date = new Date(value);
  if (Number.isNaN(date.getTime())) return "記録なし";
  return new Intl.DateTimeFormat("ja-JP", { dateStyle: "medium" }).format(date);
}

function countList(counts) {
  var entries = Object.entries(counts || {});
  if (!entries.length) return "記録なし";
  return entries.map(function (entry) { return entry[0] + "（" + entry[1] + "件）"; }).join("、");
}

function fact(label, value) {
  var node = document.createElement("div");
  var term = document.createElement("span");
  var data = document.createElement("strong");
  node.className = "photo-fact";
  term.textContent = label;
  data.textContent = value;
  node.appendChild(term);
  node.appendChild(data);
  return node;
}

function render(data, el) {
  el.summary.replaceChildren();
  el.limitations.replaceChildren();
  if (data.connection_status !== "available") {
    el.status.textContent = "写真サービスに接続できません";
    el.status.classList.add("error");
  } else {
    el.status.textContent = "更新済み " + formatDate(data.observed_at);
    el.status.classList.remove("error");
  }
  el.summary.appendChild(fact("写真", data.photo_count + "件"));
  el.summary.appendChild(fact("撮影日", data.day_count + "日分"));
  el.summary.appendChild(fact("期間", formatDate(data.oldest_photo_at) + " 〜 " + formatDate(data.newest_photo_at)));
  el.summary.appendChild(fact("位置情報あり", data.has_location_count + "件"));
  el.summary.appendChild(fact("人物情報あり", data.has_faces_count + "件"));
  el.summary.appendChild(fact("カメラ", countList(data.camera_model_counts)));

  var title = document.createElement("h4");
  var list = document.createElement("ul");
  title.textContent = "この表示について";
  (data.limitations || []).forEach(function (message) {
    var item = document.createElement("li");
    item.textContent = message;
    list.appendChild(item);
  });
  el.limitations.appendChild(title);
  el.limitations.appendChild(list);
}

async function load(force) {
  var el = elements();
  if (!el.screen || el.screen.hidden || loading || (loaded && !force)) return;
  loading = true;
  el.refresh.disabled = true;
  el.status.textContent = "読み込み中…";
  el.status.classList.remove("error");
  try {
    var data = await api("/api/photo/recent-summary?days=" + encodeURIComponent(el.days.value));
    render(data, el);
    loaded = true;
  } catch (error) {
    el.status.textContent = error.message;
    el.status.classList.add("error");
  } finally {
    loading = false;
    el.refresh.disabled = false;
  }
}

function bind() {
  var el = elements();
  if (!el.screen) return;
  el.refresh.addEventListener("click", function () { load(true); });
  el.days.addEventListener("change", function () { loaded = false; load(true); });
  window.addEventListener("jarvis:screenchange", function (event) {
    if (event.detail && event.detail.screenId === "photo-screen") {
      window.setTimeout(function () { load(false); }, 0);
    }
  });
  window.setTimeout(function () { load(false); }, 0);
}

if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", bind);
else bind();
