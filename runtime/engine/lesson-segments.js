export const LESSON_SEGMENT_VERSION = "1.1.0";

export function normalizeMeasuresPerSegment(value, fallback = null) {
  const parsed = Number(value);
  return Number.isInteger(parsed) && parsed >= 1 && parsed <= 8 ? parsed : fallback;
}

function sortedScoreMeasures(score) {
  return [...(score?.measures ?? [])]
    .filter((measure) => Number.isInteger(Number(measure?.number)))
    .sort((a, b) => Number(a.number) - Number(b.number));
}

export function resolveMeasureOrigin(score, measuresInput = null) {
  const measures = measuresInput ?? sortedScoreMeasures(score);
  if (!measures.length) return null;
  const requested = Number(score?.measureOrigin?.sourceMeasure);
  return measures.some((measure) => Number(measure.number) === requested)
    ? requested
    : Number(measures[0].number);
}

export function logicalMeasureNumber(score, sourceMeasure, measuresInput = null) {
  const measures = measuresInput ?? sortedScoreMeasures(score);
  const origin = resolveMeasureOrigin(score, measures);
  const originIndex = measures.findIndex((measure) => Number(measure.number) === origin);
  const sourceIndex = measures.findIndex((measure) => Number(measure.number) === Number(sourceMeasure));
  if (originIndex < 0 || sourceIndex < 0) return null;
  return sourceIndex - originIndex + 1;
}

export function buildLessonSegments(score, measuresPerSegment = score?.teachingConfig?.singingMeasuresPerUnit) {
  const size = normalizeMeasuresPerSegment(measuresPerSegment);
  if (!size) return [];
  const allMeasures = sortedScoreMeasures(score);
  const origin = resolveMeasureOrigin(score, allMeasures);
  const originIndex = allMeasures.findIndex((measure) => Number(measure.number) === origin);
  const measures = originIndex >= 0 ? allMeasures.slice(originIndex) : allMeasures;
  const segments = [];
  for (let index = 0; index < measures.length; index += size) {
    const chunk = measures.slice(index, index + size);
    if (!chunk.length) continue;
    const startMeasure = Number(chunk[0].number);
    const endMeasure = Number(chunk.at(-1).number);
    const logicalStartMeasure = index + 1;
    const logicalEndMeasure = index + chunk.length;
    segments.push({
      segmentId: `lesson_segment_m${String(startMeasure).padStart(3, "0")}_m${String(endMeasure).padStart(3, "0")}`,
      index: segments.length,
      label: logicalStartMeasure === logicalEndMeasure
        ? `第 ${logicalStartMeasure} 小节`
        : `第 ${logicalStartMeasure}–${logicalEndMeasure} 小节`,
      startMeasure,
      endMeasure,
      logicalStartMeasure,
      logicalEndMeasure,
      sourceMeasureOrigin: origin,
      leadInMeasureCount: Math.max(0, originIndex),
      measureCount: chunk.length,
      measures: chunk.map((measure) => Number(measure.number))
    });
  }
  return segments;
}
