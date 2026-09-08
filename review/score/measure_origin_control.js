import { loadScore, saveDraft } from "./adapters/local_workspace_adapter.js";

function escapeHtml(value) {
  return String(value ?? "").replace(/[&<>"']/g, (character) => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;"
  })[character]);
}

function lyricHint(measure) {
  const text = (measure?.notes ?? [])
    .filter((note) => !note.rest && !note.lyricContinuation && note.lyric)
    .map((note) => String(note.lyric).trim())
    .filter(Boolean)
    .join("");
  return text ? ` · ${text.slice(0, 8)}` : " · 无歌词/前导音";
}

async function mount() {
  const container = document.querySelector("#score-origin-control");
  if (!container) return;
  const params = new URLSearchParams(location.search);
  const songId = params.get("songId");
  if (!songId) {
    container.hidden = true;
    return;
  }

  try {
    const score = await loadScore(songId);
    const measures = [...(score?.measures ?? [])]
      .filter((measure) => Number.isInteger(Number(measure?.number)))
      .sort((a, b) => Number(a.number) - Number(b.number));
    if (!measures.length) {
      container.hidden = true;
      return;
    }

    const requested = Number(score?.measureOrigin?.sourceMeasure);
    const current = measures.some((measure) => Number(measure.number) === requested)
      ? requested
      : Number(measures[0].number);
    const currentIndex = measures.findIndex((measure) => Number(measure.number) === current);
    const leadInCount = Math.max(0, currentIndex);
    const status = leadInCount
      ? `当前：谱面第 ${current} 小节作为教学第1小节；前面 ${leadInCount} 个小节作为前导段。`
      : "当前：从谱面第一个小节开始，前面没有前导段。";

    container.hidden = false;
    container.innerHTML = `
      <div class="score-live-preview-head">
        <div>
          <strong>设置小节起点</strong>
          <small>如果简谱前面有前奏、弱起或无歌词的前导音，可以指定“真正的第1小节”从哪里开始。前面的内容仍保留在乐谱里，但不进入课堂教学分段和原曲小节对齐。</small>
        </div>
      </div>
      <div style="display:flex;gap:12px;align-items:end;flex-wrap:wrap;padding:14px 0 4px">
        <label style="display:grid;gap:6px;min-width:260px">
          <span>把哪个谱面小节作为教学第1小节？</span>
          <select data-measure-origin-select>
            ${measures.map((measure, index) => `<option value="${Number(measure.number)}" ${Number(measure.number) === current ? "selected" : ""}>谱面第 ${Number(measure.number)} 小节${escapeHtml(lyricHint(measure))}${index === 0 ? "（默认）" : ""}</option>`).join("")}
          </select>
        </label>
        <button class="button secondary" type="button" data-save-measure-origin>设为第1小节</button>
      </div>
      <small data-measure-origin-status>${escapeHtml(status)}</small>
    `;

    const select = container.querySelector("[data-measure-origin-select]");
    const button = container.querySelector("[data-save-measure-origin]");
    const statusNode = container.querySelector("[data-measure-origin-status]");
    select.addEventListener("change", () => {
      const selected = Number(select.value);
      const index = measures.findIndex((measure) => Number(measure.number) === selected);
      statusNode.textContent = index > 0
        ? `将把谱面第 ${selected} 小节作为教学第1小节；前面 ${index} 个小节作为前导段。`
        : "将从谱面第一个小节开始。";
    });
    button.addEventListener("click", async () => {
      const selected = Number(select.value);
      if (!measures.some((measure) => Number(measure.number) === selected)) return;
      button.disabled = true;
      button.textContent = "正在保存…";
      try {
        const next = structuredClone(score);
        next.measureOrigin = {
          sourceMeasure: selected,
          logicalMeasure: 1,
          source: "teacher",
          updatedAt: new Date().toISOString()
        };
        await saveDraft(songId, next);
        statusNode.textContent = "已保存。正在按新的第1小节重新载入校谱与音频对齐…";
        location.reload();
      } catch (error) {
        button.disabled = false;
        button.textContent = "设为第1小节";
        statusNode.textContent = `保存失败：${error.message}`;
      }
    });
  } catch (error) {
    container.hidden = false;
    container.innerHTML = `<div class="alignment-error">小节起点设置无法载入：${escapeHtml(error.message)}</div>`;
  }
}

if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", mount, { once: true });
else mount();
