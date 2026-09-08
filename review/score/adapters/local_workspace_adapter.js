const params = new URLSearchParams(location.search);
const token = params.get("token") || "";

async function request(path, options = {}) {
  if (!token) throw new Error("Score Review session token 缺失。");
  const separator = path.includes("?") ? "&" : "?";
  const response = await fetch(`${path}${separator}token=${encodeURIComponent(token)}`, {
    ...options,
    headers: { "Content-Type": "application/json", ...(options.headers || {}) },
    cache: "no-store",
  });
  const payload = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(payload.error?.message || payload.error || `请求失败（${response.status}）`);
  return payload.data ?? payload;
}

function asset(path) { return `${path}${path.includes("?") ? "&" : "?"}token=${encodeURIComponent(token)}`; }

export async function loadScore(songId) { return (await request(`/bridge/score?songId=${encodeURIComponent(songId)}`)).score; }
export async function saveDraft(songId, score) { return request(`/bridge/score/draft?songId=${encodeURIComponent(songId)}`, { method: "PUT", body: JSON.stringify(score) }); }
export async function markReviewed(songId, score) { return request(`/bridge/score/reviewed?songId=${encodeURIComponent(songId)}`, { method: "PUT", body: JSON.stringify(score) }); }
export async function verifyScore(songId, score) { return request(`/bridge/score/verified?songId=${encodeURIComponent(songId)}`, { method: "PUT", body: JSON.stringify(score) }); }
export async function recognizeLyrics(songId) { return request(`/bridge/recognize-lyrics?songId=${encodeURIComponent(songId)}`, { method: "POST", body: "{}" }); }
export async function loadSourceImage(songId) { return asset(`/bridge/source-image?songId=${encodeURIComponent(songId)}`); }
export async function loadOriginalAudio(songId) { return asset(`/bridge/original-audio?songId=${encodeURIComponent(songId)}`); }
export async function loadMeasureAlignment(songId) { return (await request(`/bridge/measure-alignment?songId=${encodeURIComponent(songId)}`)).alignment; }
export async function saveMeasureAlignment(songId, alignment) { return (await request(`/bridge/measure-alignment?songId=${encodeURIComponent(songId)}`, { method: "PUT", body: JSON.stringify(alignment) })).alignment; }
export async function getQwenStatus() { return request("/bridge/qwen-status"); }
export async function closeReviewSession() { return request("/bridge/close", { method: "POST", body: "{}" }); }
