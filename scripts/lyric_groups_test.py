#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
SCORE_RECOGNITION = ROOT / "runtime" / "score_recognition"
if str(SCORE_RECOGNITION) not in sys.path:
    sys.path.insert(0, str(SCORE_RECOGNITION))

from score_normalizer import normalize_score  # noqa: E402


def note(degree: int, beat: float, duration: float, *, lyric: str | None = None) -> dict:
    value = {
        "degree": degree,
        "octave": 0,
        "beat": beat,
        "duration": duration,
        "rest": False,
        "confidence": 1,
    }
    if lyric is not None:
        value["lyric"] = lyric
    return value


def main() -> int:
    candidate = {
        "title": "lyric groups test",
        "tonic": "C",
        "mode": "major",
        "meter": {"beats": 2, "unit": 4},
        "bpm": 72,
        "confidence": 1,
        "measures": [
            {
                "number": 1,
                "notes": [note(1, 0, 0.5), note(2, 0.5, 0.5), note(3, 1, 1)],
                "lyricGroups": [
                    {"text": "我", "noteIndex": 0, "spanNotes": 1, "confidence": 1},
                    {"text": "们", "noteIndex": 1, "spanNotes": 2, "confidence": 1},
                ],
            },
            {
                "number": 2,
                "notes": [note(4, 0, 1), note(5, 1, 1)],
                "lyricGroups": [
                    {"text": "中国", "noteIndex": 0, "spanNotes": 1, "confidence": 1},
                    {"text": "强", "noteIndex": 1, "spanNotes": 1, "confidence": 1},
                ],
            },
            {
                "number": 3,
                "notes": [note(5, 0, 1, lyric="不应使用"), note(1, 1, 1, lyric="旧字段")],
                "lyricGroups": [],
            },
            {
                "number": 4,
                "notes": [note(2, 0, 1), note(3, 1, 1)],
                "lyricGroups": [
                    {"text": "错", "noteIndex": 9, "spanNotes": 1, "confidence": 1},
                ],
            },
            {
                "number": 5,
                "notes": [note(4, 0, 1), note(5, 1, 1)],
                "lyricGroups": [
                    {"text": "重新", "noteIndex": 0, "spanNotes": 1, "confidence": 1},
                    {"text": "对齐", "noteIndex": 1, "spanNotes": 1, "confidence": 1},
                ],
            },
        ],
    }

    score = normalize_score(candidate, "lyric-groups-test", "fixture")
    assert score["recognitionMetadata"]["lyricAlignmentMode"] == "measure_local_groups"

    m1 = score["measures"][0]["notes"]
    assert m1[0]["lyric"] == "我"
    assert m1[1]["lyric"] == "们"
    assert m1[2]["lyric"] is None and m1[2]["lyricContinuation"] is True
    assert m1[1]["lyricSyllableId"] == m1[2]["lyricSyllableId"]

    m2 = score["measures"][1]["notes"]
    assert m2[0]["lyric"] == "中国", "一个音符必须允许多个歌词字"
    assert m2[1]["lyric"] == "强"

    m3 = score["measures"][2]["notes"]
    assert all(item["lyric"] is None for item in m3), "新格式存在时不得回退到 note-level lyric 平铺"

    m4 = score["measures"][3]["notes"]
    assert all(item["lyric"] is None for item in m4), "无效的本小节歌词组应局部失败"
    assert any(item["code"] == "INVALID_LYRIC_GROUP" for item in score["warnings"])

    m5 = score["measures"][4]["notes"]
    assert [item["lyric"] for item in m5] == ["重新", "对齐"], "前一小节错误不得让后一小节整体错位"

    legacy = {
        "title": "legacy",
        "tonic": "C",
        "mode": "major",
        "meter": {"beats": 2, "unit": 4},
        "bpm": 72,
        "confidence": 1,
        "measures": [{
            "number": 1,
            "notes": [note(1, 0, 1, lyric="旧"), note(2, 1, 1, lyric="版")],
        }],
    }
    legacy_score = normalize_score(legacy, "legacy-test", "fixture")
    assert legacy_score["recognitionMetadata"]["lyricAlignmentMode"] == "legacy_note_fields"
    assert [item["lyric"] for item in legacy_score["measures"][0]["notes"]] == ["旧", "版"]

    print("lyric_groups_test: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
