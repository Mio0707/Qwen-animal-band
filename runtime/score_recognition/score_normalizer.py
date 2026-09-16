"""Normalize Qwen numbered-score recognition into an auditable draft score."""

from __future__ import annotations

import argparse
import json
import math
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

SOLFEGE = ("rest", "do", "re", "mi", "fa", "sol", "la", "si")
MAJOR_INTERVALS = (0, 0, 2, 4, 5, 7, 9, 11)
MINOR_INTERVALS = (0, 0, 2, 3, 5, 7, 8, 10)
TONIC_SEMITONES = {
    "C": 0, "C#": 1, "DB": 1, "D": 2, "D#": 3, "EB": 3,
    "E": 4, "F": 5, "F#": 6, "GB": 6, "G": 7, "G#": 8,
    "AB": 8, "A": 9, "A#": 10, "BB": 10, "B": 11,
}
SHARP_NAMES = ("C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B")
FLAT_NAMES = ("C", "Db", "D", "Eb", "E", "F", "Gb", "G", "Ab", "A", "Bb", "B")


def as_number(value: Any, fallback: float) -> float:
    try:
        number = float(value)
        return number if math.isfinite(number) else fallback
    except (TypeError, ValueError):
        return fallback


def warning(code: str, severity: str, path: str, message: str) -> dict[str, str]:
    return {"code": code, "severity": severity, "path": path, "message": message}


def normalize_tonic(value: Any, warnings: list[dict[str, str]]) -> str:
    tonic = str(value or "C").strip().upper().replace("♭", "B").replace("♯", "#")
    if tonic not in TONIC_SEMITONES:
        warnings.append(warning("MISSING_PITCH", "blocking", "tonic", f"无法识别调号 {tonic!r}，已临时使用 C。"))
        return "C"
    return tonic[0] + tonic[1:].replace("B", "b")


def pitch_data(tonic: str, mode: str, degree: int, octave: int) -> tuple[str | None, int | None, float | None]:
    if degree == 0:
        return None, None, None
    tonic_key = tonic.upper().replace("b", "B")
    intervals = MINOR_INTERVALS if mode == "minor" else MAJOR_INTERVALS
    midi_number = 60 + TONIC_SEMITONES[tonic_key] + intervals[degree] + octave * 12
    names = FLAT_NAMES if "b" in tonic else SHARP_NAMES
    absolute_pitch = f"{names[midi_number % 12]}{midi_number // 12 - 1}"
    frequency = round(440 * (2 ** ((midi_number - 69) / 12)), 3)
    return absolute_pitch, midi_number, frequency


def normalize_meter(candidate: Any, warnings: list[dict[str, str]]) -> tuple[dict[str, int], float]:
    raw_meter = candidate if isinstance(candidate, dict) else {}
    raw_beats = as_number(raw_meter.get("beats"), 4)
    raw_unit = as_number(raw_meter.get("unit"), 4)
    beats = int(raw_beats)
    unit = int(raw_unit)
    if beats < 1 or beats > 12 or unit not in (2, 4, 8, 16):
        warnings.append(warning("INVALID_METER", "blocking", "meter", "拍号无效，已临时归一化为 4/4。"))
        beats, unit = 4, 4
    return {"beats": beats, "unit": unit}, beats * 4 / unit


def integer_field(value: Any) -> int | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(number) or not number.is_integer():
        return None
    return int(number)


def apply_measure_lyric_groups(
    raw_measure: dict[str, Any],
    normalized_notes: list[dict[str, Any]],
    measure_index: int,
    warnings: list[dict[str, str]],
    lyric_syllable_index: int,
) -> tuple[int, list[str]]:
    raw_groups = raw_measure.get("lyricGroups")
    if not isinstance(raw_groups, list):
        warnings.append(warning(
            "MISSING_MEASURE_LYRIC_GROUPS",
            "warning",
            f"measures[{measure_index}].lyricGroups",
            "该小节缺少 lyricGroups；已保留为空，请在人工校谱时检查歌词。",
        ))
        raw_groups = []

    occupied: set[int] = set()
    recognized: list[str] = []
    for group_index, raw_group in enumerate(raw_groups[:256]):
        path = f"measures[{measure_index}].lyricGroups[{group_index}]"
        if not isinstance(raw_group, dict):
            warnings.append(warning("INVALID_LYRIC_GROUP", "warning", path, "歌词组格式无效，已忽略。"))
            continue

        text = str(raw_group.get("text") or "").strip()
        note_index = integer_field(raw_group.get("noteIndex"))
        span_notes = integer_field(raw_group.get("spanNotes"))
        if not text:
            warnings.append(warning("INVALID_LYRIC_GROUP", "warning", f"{path}.text", "歌词组缺少文字，已忽略。"))
            continue
        if note_index is None or not (0 <= note_index < len(normalized_notes)):
            warnings.append(warning(
                "INVALID_LYRIC_GROUP",
                "warning",
                f"{path}.noteIndex",
                "歌词组 noteIndex 必须是当前小节内有效的零基音符索引，已忽略。",
            ))
            continue
        if span_notes is None or span_notes < 1:
            warnings.append(warning(
                "INVALID_LYRIC_GROUP",
                "warning",
                f"{path}.spanNotes",
                "歌词组 spanNotes 必须是大于等于 1 的整数，已忽略。",
            ))
            continue

        end_index = note_index + span_notes
        if end_index > len(normalized_notes):
            warnings.append(warning(
                "INVALID_LYRIC_GROUP",
                "warning",
                f"{path}.spanNotes",
                "歌词组超出当前小节范围，已忽略；不要把歌词延伸到下一小节。",
            ))
            continue

        indexes = list(range(note_index, end_index))
        if any(normalized_notes[index]["rest"] for index in indexes):
            warnings.append(warning(
                "INVALID_LYRIC_GROUP",
                "warning",
                path,
                "歌词组覆盖到休止符，已忽略，请人工核对。",
            ))
            continue
        if occupied.intersection(indexes):
            warnings.append(warning(
                "OVERLAPPING_LYRIC_GROUP",
                "warning",
                path,
                "歌词组与同一小节内已有歌词组重叠，已忽略。",
            ))
            continue

        lyric_syllable_index += 1
        syllable_id = f"syllable_{lyric_syllable_index:03d}"
        root = normalized_notes[note_index]
        root["lyric"] = text
        root["lyricSyllableId"] = syllable_id
        root["lyricContinuation"] = False
        for follower_index in indexes[1:]:
            follower = normalized_notes[follower_index]
            follower["lyric"] = None
            follower["lyricSyllableId"] = syllable_id
            follower["lyricContinuation"] = True

        occupied.update(indexes)
        recognized.append(text)

    return lyric_syllable_index, recognized


def expand_compact_inference(candidate: dict[str, Any]) -> dict[str, Any]:
    """Expand compact QwenWork transcription into the legacy verbose shape.

    Supports both whole-page compact v1 and layout-aware system v1. System v1 is
    flattened deterministically in source order before note expansion, so the model
    never has to merge or globally renumber independently recognized systems.
    """
    if not isinstance(candidate, dict):
        return candidate

    if candidate.get("schema") == "animal-band-score-systems-v1":
        flattened = dict(candidate)
        flattened["schema"] = "animal-band-score-compact-v1"
        flattened_measures: list[dict[str, Any]] = []
        warnings = list(candidate.get("warnings") or [])
        next_number = 1
        systems = [item for item in candidate.get("systems") or [] if isinstance(item, dict)]
        systems.sort(key=lambda item: integer_field(item.get("systemIndex")) or 10_000)
        for system in systems:
            system_index = integer_field(system.get("systemIndex"))
            for raw_measure in system.get("measures") or []:
                if not isinstance(raw_measure, dict):
                    continue
                measure = dict(raw_measure)
                supplied = integer_field(measure.get("n", measure.get("number")))
                if supplied is not None and supplied >= next_number:
                    number = supplied
                else:
                    number = next_number
                measure["n"] = number
                next_number = number + 1
                flattened_measures.append(measure)
            for message in system.get("w") or []:
                if str(message).strip():
                    warnings.append(f"system {system_index or '?'}: {str(message).strip()}")
        flattened["measures"] = flattened_measures
        flattened["warnings"] = warnings
        flattened.pop("systems", None)
        candidate = flattened

    if candidate.get("schema") not in {"animal-band-score-compact-v1", "compact-v1"}:
        return candidate

    expanded = dict(candidate)
    raw_meter = candidate.get("meter")
    if isinstance(raw_meter, str) and "/" in raw_meter:
        left, right = raw_meter.split("/", 1)
        try:
            expanded["meter"] = {"beats": int(left), "unit": int(right)}
        except ValueError:
            pass
    elif isinstance(raw_meter, (list, tuple)) and len(raw_meter) >= 2:
        expanded["meter"] = {"beats": raw_meter[0], "unit": raw_meter[1]}

    expanded_measures = []
    compact_warnings = list(candidate.get("warnings") or [])
    for measure_index, raw_measure in enumerate(candidate.get("measures") or []):
        if not isinstance(raw_measure, dict):
            continue
        raw_notes = raw_measure.get("x") if isinstance(raw_measure.get("x"), list) else raw_measure.get("notes")
        notes = []
        sequential_beat = 0.0
        uncertain_indexes = set()
        for value in raw_measure.get("u") or []:
            try:
                uncertain_indexes.add(int(value))
            except (TypeError, ValueError):
                continue
        for note_index, raw_note in enumerate(raw_notes or []):
            if isinstance(raw_note, dict):
                notes.append(raw_note)
                sequential_beat = max(
                    sequential_beat,
                    as_number(raw_note.get("beat"), sequential_beat) + as_number(raw_note.get("duration"), 1),
                )
                continue
            if not isinstance(raw_note, (list, tuple)) or len(raw_note) < 3:
                compact_warnings.append(f"m{measure_index + 1}: note {note_index + 1} compact tuple invalid")
                continue
            degree, octave, duration = raw_note[0], raw_note[1], raw_note[2]
            beat = raw_note[3] if len(raw_note) >= 4 and raw_note[3] is not None else sequential_beat
            note = {
                "degree": degree,
                "octave": octave,
                "duration": duration,
                "beat": beat,
                "rest": int(as_number(degree, 0)) == 0,
            }
            if note_index in uncertain_indexes:
                note["_recognitionUncertain"] = True
            notes.append(note)
            sequential_beat = max(sequential_beat, as_number(beat, sequential_beat) + as_number(duration, 1))

        raw_groups = raw_measure.get("l") if isinstance(raw_measure.get("l"), list) else raw_measure.get("lyricGroups")
        lyric_groups = []
        for group_index, raw_group in enumerate(raw_groups or []):
            if isinstance(raw_group, dict):
                lyric_groups.append(raw_group)
                continue
            if not isinstance(raw_group, (list, tuple)) or len(raw_group) < 3:
                compact_warnings.append(f"m{measure_index + 1}: lyric group {group_index + 1} compact tuple invalid")
                continue
            lyric_groups.append({
                "text": raw_group[0],
                "noteIndex": raw_group[1],
                "spanNotes": raw_group[2],
            })

        for message in raw_measure.get("w") or []:
            if str(message).strip():
                compact_warnings.append(f"m{raw_measure.get('n', measure_index + 1)}: {str(message).strip()}")
        expanded_measures.append({
            "number": raw_measure.get("n", raw_measure.get("number", measure_index + 1)),
            "pickup": bool(raw_measure.get("p", raw_measure.get("pickup", False))),
            "notes": notes,
            "lyricGroups": lyric_groups,
        })

    expanded["measures"] = expanded_measures
    expanded["warnings"] = compact_warnings
    expanded.pop("confidence", None)
    expanded.pop("schema", None)
    return expanded


def normalize_score(
    candidate: dict[str, Any],
    song_id: str,
    source_reference: str,
    *,
    title: str | None = None,
    model: str = "qwenwork-native",
    recognized_at: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    if not isinstance(candidate, dict):
        raise ValueError("QwenWork inference 没有返回有效的乐谱对象。")
    candidate = expand_compact_inference(candidate)

    warnings: list[dict[str, str]] = []
    meter, expected_measure_beats = normalize_meter(candidate.get("meter"), warnings)
    tonic = normalize_tonic(candidate.get("tonic") or candidate.get("key"), warnings)
    mode = str(candidate.get("mode") or "major").lower()
    if mode not in {"major", "minor", "dorian", "mixolydian", "pentatonic", "other"}:
        mode = "other"
    raw_bpm = candidate.get("bpm")
    bpm = int(as_number(raw_bpm, 72))
    if raw_bpm in (None, ""):
        warnings.append(warning("BPM_NOT_IN_SCORE", "info", "bpm", "谱面未提供 BPM，草稿暂用 72，需人工确认。"))
    bpm = max(20, min(300, bpm))

    for item in candidate.get("warnings", []):
        if str(item).strip():
            warnings.append(warning("RECOGNITION_WARNING", "warning", "recognition.raw", str(item).strip()))

    raw_measures = candidate.get("measures")
    if not isinstance(raw_measures, list) or not raw_measures:
        raise ValueError("Qwen 输出中没有可用 measures。")

    measure_local_lyrics = any(isinstance(item, dict) and "lyricGroups" in item for item in raw_measures)
    measures: list[dict[str, Any]] = []
    absolute_offset = 0.0
    lyric_syllable_index = 0
    previous_lyric: str | None = None
    previous_syllable_id: str | None = None
    recognized_lyrics: list[str] = []

    for measure_index, raw_measure in enumerate(raw_measures[:256]):
        if not isinstance(raw_measure, dict):
            continue
        number = int(as_number(raw_measure.get("number"), measure_index + 1))
        pickup = bool(raw_measure.get("pickup"))
        normalized_notes: list[dict[str, Any]] = []
        sequential_beat = 0.0
        raw_notes = raw_measure.get("notes") if isinstance(raw_measure.get("notes"), list) else []

        for note_index, raw_note in enumerate(raw_notes[:256]):
            if not isinstance(raw_note, dict):
                continue
            path = f"measures[{measure_index}].notes[{note_index}]"
            raw_degree = int(as_number(raw_note.get("degree"), 0))
            if raw_degree < 0 or raw_degree > 7:
                warnings.append(warning("INVALID_DEGREE", "blocking", f"{path}.degree", f"音级 {raw_degree} 超出 0–7。"))
            degree = max(0, min(7, raw_degree))
            rest = bool(raw_note.get("rest")) or degree == 0
            degree = 0 if rest else degree

            raw_octave = int(as_number(raw_note.get("octave"), 0))
            if raw_octave < -3 or raw_octave > 3:
                warnings.append(warning("INVALID_OCTAVE", "blocking", f"{path}.octave", f"八度 {raw_octave} 超出 -3–3。"))
            octave = 0 if rest else max(-3, min(3, raw_octave))

            raw_duration = as_number(raw_note.get("duration"), 1)
            if raw_duration <= 0:
                warnings.append(warning("INVALID_DURATION", "blocking", f"{path}.duration", "时值必须大于 0，已临时使用 1 拍。"))
            duration = round(raw_duration if raw_duration > 0 else 1, 3)
            beat = round(max(0, as_number(raw_note.get("beat"), sequential_beat)), 3)
            sequential_beat = max(sequential_beat, beat + duration)
            if bool(raw_note.get("_recognitionUncertain") or raw_note.get("uncertain")):
                warnings.append(warning("RECOGNITION_UNCERTAIN", "warning", path, "该音符视觉识别存在不确定，请人工核对。"))

            lyric = None
            lyric_continuation = False
            lyric_syllable_id = None
            if not measure_local_lyrics:
                lyric = raw_note.get("lyric")
                lyric = str(lyric) if lyric not in (None, "") else None
                lyric_continuation = bool(raw_note.get("lyricContinuation")) and not rest
                if rest and lyric:
                    warnings.append(warning("LYRIC_ON_REST", "blocking", f"{path}.lyric", "休止符不能绑定歌词，已移除。"))
                    lyric = None
                if lyric_continuation and previous_lyric and previous_syllable_id:
                    lyric = None
                    lyric_syllable_id = previous_syllable_id
                elif lyric:
                    lyric_continuation = False
                    lyric_syllable_index += 1
                    lyric_syllable_id = f"syllable_{lyric_syllable_index:03d}"
                    recognized_lyrics.append(lyric)
                    previous_lyric = lyric
                    previous_syllable_id = lyric_syllable_id
                else:
                    lyric_continuation = False

            absolute_pitch, midi_number, frequency = pitch_data(tonic, mode, degree, octave)
            normalized_notes.append({
                "noteId": f"m{number:03d}_n{note_index + 1:03d}",
                "degree": degree,
                "octave": octave,
                "pitch": absolute_pitch,
                "absolutePitch": absolute_pitch,
                "midiNumber": midi_number,
                "frequency": frequency,
                "solfege": SOLFEGE[degree],
                "duration": duration,
                "beat": beat,
                "startBeat": round(absolute_offset + beat, 3),
                "rest": rest,
                "lyric": lyric,
                "lyricSyllableId": lyric_syllable_id,
                "lyricContinuation": lyric_continuation,
            })

        if not normalized_notes:
            continue
        if measure_local_lyrics:
            lyric_syllable_index, local_lyrics = apply_measure_lyric_groups(raw_measure, normalized_notes, measure_index, warnings, lyric_syllable_index)
            recognized_lyrics.extend(local_lyrics)

        content_duration = round(max(note["beat"] + note["duration"] for note in normalized_notes), 3)
        if abs(content_duration - expected_measure_beats) > 0.001:
            warnings.append(warning(
                "MEASURE_DURATION_MISMATCH", "warning", f"measures[{measure_index}].notes",
                f"第 {number} 小节共 {content_duration} 拍，拍号通常为 {expected_measure_beats} 拍；如原谱如此可直接确认。",
            ))
        measures.append({"number": number, "pickup": pickup, "notes": normalized_notes})
        absolute_offset += content_duration

    if not measures:
        raise ValueError("Qwen 输出中没有可用音符。")

    timestamp = recognized_at or datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    raw_lyrics_text = candidate.get("lyricsText")
    lyrics_text = str(raw_lyrics_text).strip() if raw_lyrics_text not in (None, "") else "".join(recognized_lyrics)
    lyric_alignment_mode = "measure_local_groups" if measure_local_lyrics else "legacy_note_fields"

    return {
        "songId": song_id,
        "title": str(title or candidate.get("title") or song_id)[:200],
        "tonic": tonic,
        "key": f"{tonic} {mode}" if mode in {"major", "minor"} else tonic,
        "mode": mode,
        "meter": meter,
        "bpm": bpm,
        "lyricsText": lyrics_text or None,
        "measures": measures,
        "source": {
            "type": "qwenwork_skill_score_inference",
            "reference": source_reference,
            "humanReviewed": False,
            "recognitionModel": model,
            "recognizedAt": timestamp,
            "reviewedAt": None,
        },
        "recognitionMetadata": {
            **{key: value for key, value in (metadata or {}).items() if key != "confidence"},
            "lyricAlignmentMode": lyric_alignment_mode,
        },
        "verificationStatus": "draft",
        "verifiedBy": None,
        "verifiedAt": None,
        "warnings": warnings,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Normalize a raw QwenWork numbered-score inference JSON file.")
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--song-id", required=True)
    parser.add_argument("--source-reference", default="recognition/raw.json")
    parser.add_argument("--title")
    parser.add_argument("--model", default="qwenwork-native")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    candidate = json.loads(args.input.read_text(encoding="utf-8"))
    score = normalize_score(candidate, args.song_id, args.source_reference, title=args.title, model=args.model)
    body = json.dumps(score, ensure_ascii=False, indent=2)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(body + "\n", encoding="utf-8")
    else:
        print(body)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
