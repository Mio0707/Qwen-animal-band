const params = new URLSearchParams(globalThis.location?.search || "");
const runtimeSession = globalThis.__ANIMAL_BAND_REVIEW_SESSION__ || {};
// QwenWork opens only the localhost root. The bridge injects a short-lived
// token into page memory so API/media requests do not depend on third-party
// iframe cookies. Query-token support remains for explicit local/debug URLs.
const token = runtimeSession.token || params.get("token") || "";

async function request(path, options = {}) {
  const separator = path.includes("?") ? "&" : "?";
  const target = token ? `${path}${separator}token=${encodeURIComponent(token)}` : path;
  const response = await fetch(target, {
    ...options,
    credentials: "same-origin",
    headers: { "Content-Type": "application/json", ...(options.headers || {}) },
    cache: "no-store",
  });
  const payload = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(payload.error?.message || payload.error || `请求失败（${response.status}）`);
  return payload.data ?? payload;
}

function asset(path) {
  if (!token) return path;
  return `${path}${path.includes("?") ? "&" : "?"}token=${encodeURIComponent(token)}`;
}

export async function loadReviewStatus() { return request("/bridge/status"); }
export async function loadScore(songId) { return (await request(`/bridge/score?songId=${encodeURIComponent(songId)}`)).score; }
export async function saveDraft(songId, score) { return request(`/bridge/score/draft?songId=${encodeURIComponent(songId)}`, { method: "PUT", body: JSON.stringify(score) }); }
export async function markReviewed(songId, score) { return request(`/bridge/score/reviewed?songId=${encodeURIComponent(songId)}`, { method: "PUT", body: JSON.stringify(score) }); }
export async function verifyScore(songId, score) {
  const result = await request(`/bridge/score/verified?songId=${encodeURIComponent(songId)}`, { method: "PUT", body: JSON.stringify(score) });
  try {
    const alignment = await loadMeasureAlignment(songId);
    if (alignment?.calibration) await saveMeasureAlignment(songId, alignment);
  } catch {
    // SCORE_ONLY has no alignment; verification must remain independent of audio.
  }
  return result;
}
export async function loadSourceImage(songId) { return asset(`/bridge/source-image?songId=${encodeURIComponent(songId)}`); }
export async function loadOriginalAudio(songId) {
  const resources = await request(`/bridge/resources?songId=${encodeURIComponent(songId)}`);
  return resources.originalAudio ? asset(`/bridge/original-audio?songId=${encodeURIComponent(songId)}`) : "";
}
export async function loadMeasureAlignment(songId) { return (await request(`/bridge/measure-alignment?songId=${encodeURIComponent(songId)}`)).alignment; }
export async function saveMeasureAlignment(songId, alignment) { return (await request(`/bridge/measure-alignment?songId=${encodeURIComponent(songId)}`, { method: "PUT", body: JSON.stringify(alignment) })).alignment; }
export async function closeReviewSession() { return request("/bridge/close", { method: "POST", body: "{}" }); }
