"""Deterministic assembly and preflight validation for Recognition Pipeline v3.

QwenWork may run several visual reads in parallel, but it never needs to merge those
results itself. Each planned region is written as a tiny JSON file and this module
assembles them into the existing compact/system inference contract.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

try:
    from .recognition_plan import PLAN_SCHEMA, plan_region_map
except ImportError:  # direct-script compatibility
    from recognition_plan import PLAN_SCHEMA, plan_region_map

HEADER_SCHEMA = "animal-band-score-header-v3"
REGION_SCHEMA = "animal-band-score-region-v3"
WHOLE_SCHEMA = "animal-band-score-compact-v1"
SYSTEMS_SCHEMA = "animal-band-score-systems-v1"


class InferenceAssemblyError(ValueError):
    def __init__(self, code: str, message: str, report: dict[str, Any] | None = None):
        super().__init__(message)
        self.code = code
        self.report = report or {}


def _read_json(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as error:
        raise InferenceAssemblyError("REGION_RESULT_MISSING", f"识谱结果文件不存在：{path}") from error
    except json.JSONDecodeError as error:
        raise InferenceAssemblyError("REGION_JSON_INVALID", f"识谱结果不是有效 JSON：{path.name}: {error}") from error
    if not isinstance(payload, dict):
        raise InferenceAssemblyError("REGION_JSON_INVALID", f"识谱结果必须是 JSON object：{path.name}")
    return payload


def _normalize_header(payload: dict[str, Any], region_id: str = "header") -> tuple[dict[str, Any], list[str]]:
    warnings: list[str] = []
    if payload.get("schema") not in {HEADER_SCHEMA, "animal-band-score-compact-v1", "compact-v1", None}:
        warnings.append(f"header schema {payload.get('schema')!r} 非标准，按可用字段读取")
    if payload.get("regionId") not in (None, region_id):
        warnings.append(f"header regionId={payload.get('regionId')!r} 与计划 {region_id!r} 不一致")
    metadata = {
        key: payload.get(key)
        for key in ("title", "tonic", "mode", "meter", "bpm")
        if payload.get(key) not in (None, "")
    }
    for item in payload.get("warnings") or []:
        if str(item).strip():
            warnings.append(str(item).strip())
    return metadata, warnings


def _normalize_system_region(payload: dict[str, Any], region: dict[str, Any]) -> tuple[dict[str, Any] | None, list[str]]:
    region_id = str(region.get("regionId"))
    expected_index = int(region.get("systemIndex"))
    warnings: list[str] = []

    if payload.get("schema") == REGION_SCHEMA:
        if payload.get("regionId") not in (None, region_id):
            return None, [f"{region_id}: regionId 与计划不一致"]
        supplied_index = payload.get("systemIndex", expected_index)
        try:
            supplied_index = int(supplied_index)
        except (TypeError, ValueError):
            return None, [f"{region_id}: systemIndex 无效"]
        if supplied_index != expected_index:
            return None, [f"{region_id}: systemIndex={supplied_index}，预期 {expected_index}"]
        measures = payload.get("measures")
        local_warnings = payload.get("warnings") or payload.get("w") or []
    elif payload.get("schema") == SYSTEMS_SCHEMA:
        systems = [item for item in payload.get("systems") or [] if isinstance(item, dict)]
        chosen = None
        for item in systems:
            try:
                if int(item.get("systemIndex")) == expected_index:
                    chosen = item
                    break
            except (TypeError, ValueError):
                continue
        if not chosen:
            return None, [f"{region_id}: aggregate 中找不到 system {expected_index}"]
        measures = chosen.get("measures")
        local_warnings = chosen.get("w") or []
    elif payload.get("schema") in {WHOLE_SCHEMA, "compact-v1", None}:
        measures = payload.get("measures")
        local_warnings = payload.get("warnings") or []
    else:
        return None, [f"{region_id}: 不支持 schema={payload.get('schema')!r}"]

    if not isinstance(measures, list) or not measures:
        return None, [f"{region_id}: measures 为空"]
    valid_measures = [item for item in measures if isinstance(item, dict)]
    if not valid_measures:
        return None, [f"{region_id}: 没有有效 measure object"]
    if len(valid_measures) != len(measures):
        warnings.append(f"{region_id}: 部分 measure 不是 object，已忽略")
    for item in local_warnings:
        if str(item).strip():
            warnings.append(f"{region_id}: {str(item).strip()}")
    return {
        "systemIndex": expected_index,
        "measures": valid_measures,
        "w": warnings.copy(),
    }, warnings


def _structural_advisories(raw: dict[str, Any]) -> list[dict[str, Any]]:
    """Cheap deterministic checks that are advisory, never proof of page coverage."""
    advisories: list[dict[str, Any]] = []
    meter = raw.get("meter")
    beats = unit = None
    if isinstance(meter, str) and "/" in meter:
        try:
            left, right = meter.split("/", 1)
            beats, unit = int(left), int(right)
        except ValueError:
            pass
    elif isinstance(meter, dict):
        try:
            beats, unit = int(meter.get("beats")), int(meter.get("unit"))
        except (TypeError, ValueError):
            pass
    expected = beats * 4 / unit if beats and unit else None

    systems = raw.get("systems") if raw.get("schema") == SYSTEMS_SCHEMA else None
    if systems is None:
        systems = [{"systemIndex": 1, "measures": raw.get("measures") or []}]
    for system in systems:
        if not isinstance(system, dict):
            continue
        system_index = system.get("systemIndex")
        for local_index, measure in enumerate(system.get("measures") or [], start=1):
            if not isinstance(measure, dict):
                continue
            notes = measure.get("x") if isinstance(measure.get("x"), list) else measure.get("notes")
            if not isinstance(notes, list) or not notes:
                advisories.append({
                    "code": "EMPTY_MEASURE",
                    "systemIndex": system_index,
                    "localMeasure": local_index,
                    "message": "小节没有可识别音符；交给人工核谱，除非该区域 JSON 本身损坏。",
                })
                continue
            if expected is not None and not measure.get("p"):
                duration_sum = 0.0
                usable = True
                for note in notes:
                    try:
                        if isinstance(note, dict):
                            duration_sum += float(note.get("duration", 0))
                        elif isinstance(note, (list, tuple)) and len(note) >= 3:
                            duration_sum += float(note[2])
                        else:
                            usable = False
                            break
                    except (TypeError, ValueError):
                        usable = False
                        break
                if usable and abs(duration_sum - expected) > 0.02:
                    advisories.append({
                        "code": "MEASURE_DURATION_MISMATCH",
                        "systemIndex": system_index,
                        "localMeasure": local_index,
                        "expectedBeats": expected,
                        "recognizedBeats": round(duration_sum, 4),
                        "message": "小节总时值与拍号不一致；这只提示人工核对，不证明漏谱，也不自动触发重识别。",
                    })
    return advisories


def assemble_from_directory(plan: dict[str, Any], inference_dir: Path) -> tuple[dict[str, Any], dict[str, Any]]:
    inference_dir = Path(inference_dir).expanduser().resolve()
    region_map = plan_region_map(plan)
    required_ids = list((plan.get("coverage") or {}).get("requiredRegionIds") or [])
    missing: list[str] = []
    invalid: list[dict[str, str]] = []
    warnings: list[str] = []

    if plan.get("strategy") == "whole_page":
        region_id = "whole-page"
        result_path = inference_dir / "whole-page.json"
        if not result_path.is_file():
            missing.append(region_id)
            report = {
                "ok": False,
                "strategy": "whole_page",
                "missingRegionIds": missing,
                "invalidRegions": invalid,
                "repairRegionIds": missing,
                "warnings": warnings,
            }
            raise InferenceAssemblyError("SCORE_SOURCE_COVERAGE_INCOMPLETE", "缺少 whole-page 识谱结果。", report)
        raw = _read_json(result_path)
        if raw.get("schema") not in {WHOLE_SCHEMA, "compact-v1"} or not isinstance(raw.get("measures"), list) or not raw.get("measures"):
            invalid.append({"regionId": region_id, "reason": "whole-page JSON 缺少有效 compact measures"})
            report = {
                "ok": False,
                "strategy": "whole_page",
                "missingRegionIds": [],
                "invalidRegions": invalid,
                "repairRegionIds": [],
                "warnings": warnings,
            }
            raise InferenceAssemblyError("SCORE_INFERENCE_INVALID", "whole-page 识谱结果结构无效。", report)
        report = {
            "ok": True,
            "strategy": "whole_page",
            "requiredRegionIds": required_ids,
            "receivedRegionIds": [region_id],
            "missingRegionIds": [],
            "invalidRegions": [],
            "repairRegionIds": [],
            "warnings": warnings,
            "advisories": _structural_advisories(raw),
        }
        return raw, report

    header_metadata: dict[str, Any] = {}
    header_path = inference_dir / "header.json"
    if "header" in region_map and header_path.is_file():
        header_metadata, header_warnings = _normalize_header(_read_json(header_path))
        warnings.extend(header_warnings)

    systems: list[dict[str, Any]] = []
    received_ids: list[str] = []
    for region_id in required_ids:
        region = region_map.get(region_id)
        if not region:
            invalid.append({"regionId": region_id, "reason": "recognition plan 缺少 region 定义"})
            continue
        result_path = inference_dir / f"{region_id}.json"
        if not result_path.is_file():
            missing.append(region_id)
            continue
        payload = _read_json(result_path)
        normalized, region_warnings = _normalize_system_region(payload, region)
        warnings.extend(region_warnings)
        if normalized is None:
            invalid.append({"regionId": region_id, "reason": "; ".join(region_warnings) or "区域结果无效"})
            continue
        systems.append(normalized)
        received_ids.append(region_id)

    repair_ids = sorted(set(missing + [item["regionId"] for item in invalid]))
    if repair_ids:
        report = {
            "ok": False,
            "strategy": "music_systems",
            "requiredRegionIds": required_ids,
            "receivedRegionIds": received_ids,
            "missingRegionIds": missing,
            "invalidRegions": invalid,
            "repairRegionIds": repair_ids,
            "warnings": warnings,
        }
        raise InferenceAssemblyError(
            "SCORE_SOURCE_COVERAGE_INCOMPLETE",
            "原图谱面区域未完整覆盖；只补识别 report.repairRegionIds，一次，不重跑其他区域。",
            report,
        )

    systems.sort(key=lambda item: int(item.get("systemIndex") or 10_000))
    raw: dict[str, Any] = {
        "schema": SYSTEMS_SCHEMA,
        **header_metadata,
        "systems": systems,
        "warnings": warnings,
    }
    report = {
        "ok": True,
        "strategy": "music_systems",
        "requiredRegionIds": required_ids,
        "receivedRegionIds": received_ids,
        "missingRegionIds": [],
        "invalidRegions": [],
        "repairRegionIds": [],
        "warnings": warnings,
        "advisories": _structural_advisories(raw),
        "systemCount": len(systems),
        "measureCount": sum(len(item.get("measures") or []) for item in systems),
    }
    return raw, report


def assemble_inference(
    plan: dict[str, Any],
    *,
    inference_input: Path | None = None,
    inference_dir: Path | None = None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    if inference_dir:
        return assemble_from_directory(plan, inference_dir)
    if not inference_input:
        raise InferenceAssemblyError("INFERENCE_INPUT_MISSING", "必须提供 inference-dir 或 inference-input。")
    raw = _read_json(Path(inference_input).expanduser().resolve())

    if plan.get("strategy") == "music_systems":
        expected = int((plan.get("coverage") or {}).get("expectedSystems") or 0)
        systems = raw.get("systems") if raw.get("schema") == SYSTEMS_SCHEMA else None
        received = set()
        if isinstance(systems, list):
            for item in systems:
                if not isinstance(item, dict) or not isinstance(item.get("measures"), list) or not item.get("measures"):
                    continue
                try:
                    index = int(item.get("systemIndex"))
                except (TypeError, ValueError):
                    continue
                if 1 <= index <= expected:
                    received.add(index)
        missing = [f"system-{index:02d}" for index in range(1, expected + 1) if index not in received]
        if missing:
            report = {
                "ok": False,
                "strategy": "music_systems",
                "missingRegionIds": missing,
                "repairRegionIds": missing,
                "invalidRegions": [],
                "warnings": [],
            }
            raise InferenceAssemblyError(
                "SCORE_SOURCE_COVERAGE_INCOMPLETE",
                "aggregate 识谱结果缺少计划中的 system。",
                report,
            )
    elif raw.get("schema") not in {WHOLE_SCHEMA, "compact-v1"} and not isinstance(raw.get("measures"), list):
        raise InferenceAssemblyError("SCORE_INFERENCE_INVALID", "whole-page inference 结构无效。")

    report = {
        "ok": True,
        "strategy": plan.get("strategy"),
        "legacyAggregateInput": True,
        "missingRegionIds": [],
        "repairRegionIds": [],
        "invalidRegions": [],
        "warnings": [],
        "advisories": _structural_advisories(raw),
    }
    return raw, report
