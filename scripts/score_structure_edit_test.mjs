import {
  deleteMeasure,
  insertEmptyMeasure,
  mergeMeasureWithNext,
  mergeMeasureWithPrevious,
  splitMeasure,
} from "../review/score/score_structure_editor.js";

function note(id) { return { noteId: id }; }
function assert(condition, message) { if (!condition) throw new Error(message); }

const score = {
  measures: [
    { number: 1, pickup: false, notes: [note("a"), note("b"), note("c"), note("d"), note("e"), note("f")] },
    { number: 2, pickup: false, notes: [note("g"), note("h")] },
  ],
  measureOrigin: { sourceMeasure: 2, logicalMeasure: 1, source: "test" },
};

let result = splitMeasure(score, 0, 3);
assert(score.measures.length === 3, "split must add a measure");
assert(score.measures[0].notes.map(n => n.noteId).join("") === "abcd", "split left mismatch");
assert(score.measures[1].notes.map(n => n.noteId).join("") === "ef", "split right mismatch");
assert(score.measures.map(m => m.number).join(",") === "1,2,3", "split must renumber");
assert(score.measureOrigin.sourceMeasure === 3, "origin after split must follow original target");
assert(result.currentMeasureIndex === 0, "split current index mismatch");

result = mergeMeasureWithNext(score, 0);
assert(score.measures.length === 2, "merge next must remove a measure");
assert(score.measures[0].notes.map(n => n.noteId).join("") === "abcdef", "merge note order mismatch");
assert(score.measureOrigin.sourceMeasure === 2, "origin after merge must follow original target");

result = insertEmptyMeasure(score, 1, "before");
assert(score.measures.length === 3 && score.measures[1].notes.length === 0, "insert before failed");
assert(score.measureOrigin.sourceMeasure === 3, "origin after insert must shift");
assert(result.currentMeasureIndex === 1, "insert current index mismatch");

deleteMeasure(score, 1);
assert(score.measures.length === 2, "delete inserted measure failed");
assert(score.measureOrigin.sourceMeasure === 2, "origin after delete must shift back");

mergeMeasureWithPrevious(score, 1);
assert(score.measures.length === 1, "merge previous failed");
assert(score.measureOrigin.sourceMeasure === 1, "origin merged into previous must follow merged measure");

let refused = false;
try { deleteMeasure(score, 0); } catch { refused = true; }
assert(refused, "must refuse deleting the final measure");

console.log(JSON.stringify({ status: "PASS", measures: score.measures.length, origin: score.measureOrigin.sourceMeasure }));
