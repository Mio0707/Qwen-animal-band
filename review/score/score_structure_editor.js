function assertScore(score) {
  if (!score || !Array.isArray(score.measures) || !score.measures.length) {
    throw new Error("乐谱缺少可编辑的小节。");
  }
}

function originIndex(score) {
  const requested = Number(score?.measureOrigin?.sourceMeasure);
  if (!Number.isInteger(requested)) return null;
  const index = score.measures.findIndex((measure) => Number(measure.number) === requested);
  return index >= 0 ? index : null;
}

function applyOriginIndex(score, index) {
  if (!score.measureOrigin || index == null || !score.measures.length) return;
  const safe = Math.max(0, Math.min(index, score.measures.length - 1));
  score.measureOrigin.sourceMeasure = safe + 1;
}

export function renumberMeasures(score) {
  assertScore(score);
  score.measures.forEach((measure, index) => { measure.number = index + 1; });
  return score;
}

export function splitMeasure(score, measureIndex, afterNoteIndex) {
  assertScore(score);
  const measure = score.measures[measureIndex];
  if (!measure) throw new Error("找不到要拆分的小节。");
  if (!Array.isArray(measure.notes) || measure.notes.length < 2) throw new Error("当前小节至少需要两个音符才能拆分。");
  if (!Number.isInteger(afterNoteIndex) || afterNoteIndex < 0 || afterNoteIndex >= measure.notes.length - 1) {
    throw new Error("请选择两个音符之间的位置拆分小节。");
  }

  const oldOrigin = originIndex(score);
  const left = { ...measure, notes: measure.notes.slice(0, afterNoteIndex + 1) };
  const right = { ...measure, pickup: false, notes: measure.notes.slice(afterNoteIndex + 1) };
  score.measures.splice(measureIndex, 1, left, right);

  let nextOrigin = oldOrigin;
  if (oldOrigin != null && oldOrigin > measureIndex) nextOrigin = oldOrigin + 1;
  renumberMeasures(score);
  applyOriginIndex(score, nextOrigin);
  return { currentMeasureIndex: measureIndex, operation: "split" };
}

export function mergeMeasureWithNext(score, measureIndex) {
  assertScore(score);
  if (measureIndex < 0 || measureIndex >= score.measures.length - 1) throw new Error("当前小节后面没有可合并的小节。");
  const oldOrigin = originIndex(score);
  const left = score.measures[measureIndex];
  const right = score.measures[measureIndex + 1];
  left.notes = [...(left.notes ?? []), ...(right.notes ?? [])];
  score.measures.splice(measureIndex + 1, 1);

  let nextOrigin = oldOrigin;
  if (oldOrigin === measureIndex + 1) nextOrigin = measureIndex;
  else if (oldOrigin != null && oldOrigin > measureIndex + 1) nextOrigin = oldOrigin - 1;
  renumberMeasures(score);
  applyOriginIndex(score, nextOrigin);
  return { currentMeasureIndex: measureIndex, operation: "merge-next" };
}

export function mergeMeasureWithPrevious(score, measureIndex) {
  if (measureIndex <= 0) throw new Error("当前小节前面没有可合并的小节。");
  const result = mergeMeasureWithNext(score, measureIndex - 1);
  return { ...result, operation: "merge-previous" };
}

export function insertEmptyMeasure(score, measureIndex, position = "after") {
  assertScore(score);
  if (!Number.isInteger(measureIndex) || measureIndex < 0 || measureIndex >= score.measures.length) throw new Error("找不到插入位置。");
  const insertAt = position === "before" ? measureIndex : measureIndex + 1;
  const oldOrigin = originIndex(score);
  score.measures.splice(insertAt, 0, { number: 0, pickup: false, notes: [] });
  const nextOrigin = oldOrigin != null && oldOrigin >= insertAt ? oldOrigin + 1 : oldOrigin;
  renumberMeasures(score);
  applyOriginIndex(score, nextOrigin);
  return { currentMeasureIndex: insertAt, operation: `insert-${position}` };
}

export function deleteMeasure(score, measureIndex) {
  assertScore(score);
  if (score.measures.length <= 1) throw new Error("乐谱至少需要保留一个小节。");
  if (!Number.isInteger(measureIndex) || measureIndex < 0 || measureIndex >= score.measures.length) throw new Error("找不到要删除的小节。");
  const oldOrigin = originIndex(score);
  score.measures.splice(measureIndex, 1);

  let nextOrigin = oldOrigin;
  if (oldOrigin === measureIndex) nextOrigin = Math.min(measureIndex, score.measures.length - 1);
  else if (oldOrigin != null && oldOrigin > measureIndex) nextOrigin = oldOrigin - 1;
  renumberMeasures(score);
  applyOriginIndex(score, nextOrigin);
  return { currentMeasureIndex: Math.min(measureIndex, score.measures.length - 1), operation: "delete" };
}

export function measureStructureSignature(score) {
  return JSON.stringify((score?.measures ?? []).map((measure) => (measure?.notes ?? []).map((note) => note.noteId ?? null)));
}
