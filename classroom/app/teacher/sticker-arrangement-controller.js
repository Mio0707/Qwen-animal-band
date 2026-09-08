import { clearStickerArrangement, normalizeStickerArrangement, stateAtSegment, stickerArrangementPayload, STICKER_TRACKS, toggleTrackAtSegment } from "../../core/sticker-arrangement-runtime.js";
import { TrackMixer } from "../../web_audio/track_mixer.js";

function parseJson(root, selector) {
  const node = root.querySelector(selector);
  try { return node ? JSON.parse(node.textContent || "null") : null; } catch { return null; }
}

function postJson(path, method, body) {
  return fetch(path, { method, headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) })
    .then(async (response) => {
      const payload = await response.json().catch(() => ({}));
      if (!response.ok) throw new Error(payload.error || `请求失败（${response.status}）`);
      return payload;
    });
}

export async function bindStickerArrangementActivity(root) {
  const host = root.querySelector("[data-sticker-arrangement-runtime]");
  if (!host) return;
  const original = parseJson(host, "[data-sticker-project]");
  const pack = parseJson(host, "[data-sticker-stem-pack]");
  const lyricsBySegmentId = parseJson(host, "[data-sticker-segment-lyrics]") ?? {};
  if (!pack || (pack.tracks?.length ?? 0) !== 4 || !(pack.tracks ?? []).every((track) => Array.isArray(track.events))) {
    throw new Error("四轨 Event JSON 尚未准备。");
  }

  const offline = document.documentElement.dataset.offlineClassroom === "true";
  const storageKey = `animal-band:offline:${host.dataset.preparationId}:sticker-arrangement`;
  let stored = null;
  if (offline) { try { stored = JSON.parse(localStorage.getItem(storageKey) || "null"); } catch {} }
  const source = stored ?? original;
  let project = normalizeStickerArrangement(source, {
    preparationId: host.dataset.preparationId,
    songId: host.dataset.songId,
    lessonSegments: source?.lessonSegments ?? original?.lessonSegments ?? [],
    tracks: STICKER_TRACKS,
  });

  const bpm = Number(pack.bpm || 96);
  const beatsPerMeasure = Number(pack.meter?.beats || 4) * 4 / Number(pack.meter?.unit || 4);
  const secondsPerBeat = 60 / bpm;
  const totalDuration = Number(pack.totalBeats ?? pack.measureCount * beatsPerMeasure) * secondsPerBeat;
  const mixer = new TrackMixer("/assets/web-sampler-v1");
  let playing = false;
  let offset = 0;
  let raf = null;
  let saveTimer = null;
  let previewSegment = 0;

  const playButton = host.querySelector("[data-sticker-play]");
  const currentLabel = host.querySelector("[data-sticker-current-segment]");
  const currentLyrics = host.querySelector("[data-sticker-current-lyrics]");
  const transport = host.querySelector("[data-sticker-transport-state]");
  const warning = host.querySelector("[data-sticker-warning]");
  const saveStatus = host.querySelector("[data-sticker-save-status]");
  const emptyStage = host.querySelector("[data-sticker-stage-empty]");

  function warn(message = "") { warning.hidden = !message; warning.textContent = message; }
  function position() { return playing ? Math.min(totalDuration, mixer.position()) : offset; }
  function indexForBeat(beat) {
    const measure = Math.max(1, Math.floor(beat / beatsPerMeasure) + 1);
    const found = project.lessonSegments.findIndex((segment) => measure >= segment.startMeasure && measure <= segment.endMeasure);
    return found >= 0 ? found : Math.max(0, project.lessonSegments.length - 1);
  }
  function indexForSeconds(seconds) { return indexForBeat(seconds / secondsPerBeat); }
  function activeAtBeat(trackId, beat) { return stateAtSegment(project, trackId, indexForBeat(beat)); }

  function render() {
    const index = playing ? indexForSeconds(position()) : previewSegment;
    const segment = project.lessonSegments[index];
    currentLabel.textContent = segment?.label || `第 ${index + 1} 段`;
    if (currentLyrics) currentLyrics.textContent = lyricsBySegmentId[segment?.segmentId] ?? "";
    transport.textContent = playing ? "正在演奏" : "准备开始";
    let activeCount = 0;
    for (const track of STICKER_TRACKS) {
      const on = stateAtSegment(project, track.trackId, index);
      if (on) activeCount += 1;
      const performer = host.querySelector(`[data-sticker-stage-performer="${track.trackId}"]`);
      if (performer) performer.hidden = !on;
      host.querySelectorAll(`[data-sticker-cell][data-track-id="${track.trackId}"]`).forEach((cell) => {
        const cellIndex = Number(cell.dataset.segmentIndex);
        const cellOn = stateAtSegment(project, track.trackId, cellIndex);
        cell.classList.toggle("on", cellOn);
        cell.classList.toggle("current", cellIndex === index);
        cell.setAttribute("aria-pressed", cellOn ? "true" : "false");
      });
    }
    emptyStage.hidden = activeCount > 0;
    host.querySelectorAll("[data-sticker-preview-segment]").forEach((head, i) => head.classList.toggle("current", i === index));
  }

  async function start({ fromStart = false } = {}) {
    warn();
    if (fromStart || offset >= totalDuration - 0.02) offset = 0;
    await mixer.play(pack, { offsetSec: offset, isTrackActive: activeAtBeat });
    playing = true;
    previewSegment = indexForSeconds(offset);
    playButton.textContent = "Ⅱ 暂停";
    tick();
  }
  function pause() {
    if (!playing) return;
    offset = position();
    playing = false;
    mixer.stop();
    if (raf) cancelAnimationFrame(raf);
    raf = null;
    playButton.textContent = "▶ 继续播放";
    previewSegment = indexForSeconds(offset);
    render();
  }
  function restart() { pause(); offset = 0; previewSegment = 0; playButton.textContent = "▶ 播放我的编排"; render(); }
  function tick() {
    if (!playing) return;
    if (position() >= totalDuration - 0.02) {
      playing = false; offset = 0; mixer.stop(); previewSegment = Math.max(0, project.lessonSegments.length - 1);
      playButton.textContent = "▶ 再听一次"; transport.textContent = "播放完成"; render(); return;
    }
    render();
    raf = requestAnimationFrame(tick);
  }
  function saveSoon() {
    saveStatus.textContent = "正在保存…";
    if (saveTimer) clearTimeout(saveTimer);
    saveTimer = setTimeout(async () => {
      try {
        const payload = stickerArrangementPayload(project);
        if (offline) localStorage.setItem(storageKey, JSON.stringify(payload));
        else await postJson(`/api/preparations/${encodeURIComponent(host.dataset.preparationId)}/sticker-arrangement`, "PUT", payload);
        saveStatus.textContent = offline ? "已保存在本机" : "已自动保存";
      } catch (error) { saveStatus.textContent = "保存失败"; warn(error.message); }
    }, 250);
  }
  async function toggleCell(trackId, index) {
    const resumeAt = playing ? position() : null;
    project = toggleTrackAtSegment(project, trackId, index);
    previewSegment = index;
    if (resumeAt !== null) { mixer.stop(); offset = resumeAt; await mixer.play(pack, { offsetSec: offset, isTrackActive: activeAtBeat }); }
    saveSoon(); render();
  }

  host.querySelectorAll("[data-sticker-cell]").forEach((cell) => cell.addEventListener("click", () => toggleCell(cell.dataset.trackId, Number(cell.dataset.segmentIndex)).catch((error) => warn(error.message))));
  host.querySelectorAll("[data-sticker-preview-segment]").forEach((head) => head.addEventListener("click", () => {
    if (playing) pause();
    previewSegment = Number(head.dataset.stickerPreviewSegment);
    offset = Math.max(0, (project.lessonSegments[previewSegment].startMeasure - 1) * beatsPerMeasure * secondsPerBeat);
    render();
  }));
  playButton.addEventListener("click", () => (playing ? pause() : start().catch((error) => warn(error.message))));
  host.querySelector("[data-sticker-restart]")?.addEventListener("click", restart);
  host.querySelector("[data-sticker-clear]")?.addEventListener("click", () => { project = clearStickerArrangement(project); if (playing) pause(); saveSoon(); render(); });
  window.addEventListener("pagehide", () => { if (saveTimer) clearTimeout(saveTimer); if (raf) cancelAnimationFrame(raf); mixer.close(); }, { once: true });
  render();
}
