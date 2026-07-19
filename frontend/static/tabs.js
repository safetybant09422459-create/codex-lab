import { refreshLogs } from "./logs.js";
import { refreshChanges } from "./review.js";
import { refreshService } from "./update.js";
import { refreshChatTraces } from "./chat-trace.js";

export function bindTabs() {
  document.querySelectorAll(".tab").forEach((tab) => {
    tab.addEventListener("click", async () => {
      document.querySelectorAll(".tab").forEach((item) => item.classList.remove("active"));
      document.querySelectorAll(".tab-panel").forEach((panel) => panel.classList.remove("active"));
      tab.classList.add("active");
      document.querySelector(`#${tab.dataset.tab}`).classList.add("active");

      if (tab.dataset.tab === "review-panel") {
        await refreshLogs();
        await refreshChanges();
      }
      if (tab.dataset.tab === "update-panel") {
        await refreshService();
      }
      if (tab.dataset.tab === "chat-trace-panel") {
        await refreshChatTraces();
      }
    });
  });
}
