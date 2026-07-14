export class ApiError extends Error {
  constructor(message, status, retryable, code) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.retryable = retryable;
    this.code = code || "request_failed";
  }
}

export async function api(path, options = {}) {
  let res;
  try {
    res = await fetch(path, options);
  } catch (_error) {
    throw new ApiError("Jarvisに接続できません", 0, true, "network_unavailable");
  }
  const data = await res.json().catch(() => ({}));
  if (!res.ok) {
    const detail = typeof data.detail === "string" ? data.detail : `HTTP ${res.status}`;
    const code = res.headers.get("X-Jarvis-Error-Code") || "request_failed";
    const retryable =
      code !== "chat_not_configured" &&
      (res.status === 408 || res.status === 429 || res.status >= 500);
    throw new ApiError(detail, res.status, retryable, code);
  }
  return data;
}
