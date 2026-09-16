"""Recognition v3 planning for numbered-score images.

The planner is intentionally deterministic. It does not recognize music and it does
not decide musical meaning. Its job is to choose stable visual regions, preserve
source coverage, and keep visual-model work bounded.

Design goals:
- one planned recognition round, with independent regions read once in parallel;
- no model-directed crop/retry loop;
- source coverage is checked from the plan, not inferred from musical self-consistency;
- dense systems get more pixels, but the semantic score contract stays unchanged;
- low-confidence/irregular layouts fall back to a whole-page region rather than
  forcing brittle segmentation.
"""
from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import json
from pathlib import Path
from statistics import median
from typing import Any

PLANNER_VERSION = "recognition-plan-v3.2-barline-first"
PLAN_SCHEMA = "animal-band-recognition-plan-v3"


@dataclass(frozen=True)
class Band:
    top: int
    bottom: int
    left: int
    right: int
    ink_density: float

    @property
    def height(self) -> int:
        return self.bottom - self.top

    @property
    def width(self) -> int:
        return self.right - self.left

    @property
    def center_y(self) -> float:
        return (self.top + self.bottom) / 2


def _load_pillow():
    try:
        from PIL import Image  # type: ignore
        return Image
    except Exception:
        return None


def pillow_available() -> bool:
    return _load_pillow() is not None


def _row_stats(gray, threshold: int = 190) -> tuple[list[int], list[int | None], list[int | None]]:
    width, height = gray.size
    px = gray.load()
    counts: list[int] = []
    mins: list[int | None] = []
    maxs: list[int | None] = []
    for y in range(height):
        count = 0
        min_x = None
        max_x = None
        for x in range(width):
            if px[x, y] < threshold:
                count += 1
                if min_x is None:
                    min_x = x
                max_x = x
        counts.append(count)
        mins.append(min_x)
        maxs.append(max_x)
    return counts, mins, maxs


def _group_ink_bands(gray) -> list[Band]:
    width, height = gray.size
    counts, mins, maxs = _row_stats(gray)
    active_threshold = max(3, round(width * 0.01))
    active = [index for index, count in enumerate(counts) if count >= active_threshold]
    if not active:
        return []

    max_gap = max(16, min(30, round(height * 0.022)))
    grouped: list[tuple[int, int]] = []
    start = previous = active[0]
    for y in active[1:]:
        if y - previous > max_gap:
            grouped.append((start, previous + 1))
            start = y
        previous = y
    grouped.append((start, previous + 1))

    bands: list[Band] = []
    for top, bottom in grouped:
        xs_min = [value for value in mins[top:bottom] if value is not None]
        xs_max = [value for value in maxs[top:bottom] if value is not None]
        if not xs_min or not xs_max:
            continue
        left = min(xs_min)
        right = max(xs_max) + 1
        ink = sum(counts[top:bottom]) / max(1, (bottom - top) * width)
        bands.append(Band(top=top, bottom=bottom, left=left, right=right, ink_density=ink))
    return bands


def _system_candidates(gray, bands: list[Band]) -> tuple[list[Band], str]:
    width, height = gray.size
    min_height = max(30, round(height * 0.035))

    def select(min_ink: float, min_width_ratio: float) -> list[Band]:
        return [
            band for band in bands
            if band.height >= min_height
            and band.width / width >= min_width_ratio
            and band.ink_density >= min_ink
        ]

    primary = select(0.043, 0.62)
    if len(primary) >= 2:
        return primary, "high"
    relaxed = select(0.030, 0.58)
    if len(relaxed) >= 2:
        return relaxed, "medium"
    return [], "low"


def _regularity(candidates: list[Band]) -> float:
    if len(candidates) < 3:
        return 1.0
    gaps = [b.center_y - a.center_y for a, b in zip(candidates, candidates[1:])]
    med = median(gaps)
    if med <= 0:
        return 0.0
    deviations = [abs(value - med) / med for value in gaps]
    return max(0.0, 1.0 - min(1.0, median(deviations) * 2.5))


def _choose_systems(gray, bands: list[Band]) -> tuple[list[Band], str]:
    candidates, confidence = _system_candidates(gray, bands)
    if not candidates:
        return [], "low"
    if len(candidates) >= 4:
        full_regularity = _regularity(candidates)
        tail_regularity = _regularity(candidates[1:])
        first_gap = candidates[1].center_y - candidates[0].center_y
        later_gaps = [b.center_y - a.center_y for a, b in zip(candidates[1:], candidates[2:])]
        later_median = median(later_gaps) if later_gaps else first_gap
        if later_median > 0 and first_gap > later_median * 1.6 and tail_regularity >= full_regularity:
            candidates = candidates[1:]
    return candidates, confidence


def _estimate_complexity(systems: list[Band]) -> str:
    if not systems:
        return "unknown"
    density = median([item.ink_density for item in systems])
    if density >= 0.082:
        return "dense"
    if density >= 0.058:
        return "medium"
    return "simple"


def _soft_barline_candidates(gray, band: Band) -> list[int]:
    """Return advisory x-centers of barline-like vertical strokes."""
    width, _ = gray.size
    px = gray.load()
    top, bottom = band.top, band.bottom
    height = max(1, bottom - top)
    hits: list[int] = []
    for x in range(max(0, band.left - 4), min(width, band.right + 4)):
        dark = 0
        longest = current = 0
        for y in range(top, bottom):
            if px[x, y] < 150:
                dark += 1
                current += 1
                longest = max(longest, current)
            else:
                current = 0
        if longest >= max(12, round(height * 0.35)) and dark >= max(12, round(height * 0.35)):
            hits.append(x)
    if not hits:
        return []
    clusters: list[list[int]] = [[hits[0]]]
    for x in hits[1:]:
        if x - clusters[-1][-1] > 3:
            clusters.append([x])
        else:
            clusters[-1].append(x)
    return [round(sum(cluster) / len(cluster)) for cluster in clusters]


def _soft_barline_hint(gray, band: Band) -> int | None:
    candidates = _soft_barline_candidates(gray, band)
    return len(candidates) or None


def _save_resized(source, box: tuple[int, int, int, int], path: Path, target_width: int) -> tuple[int, int, float]:
    Image = _load_pillow()
    assert Image is not None
    crop = source.crop(box)
    scale = 1.0
    if crop.width < target_width:
        scale = min(4.0, target_width / max(1, crop.width))
        new_width = max(crop.width, round(crop.width * scale))
        new_height = max(crop.height, round(crop.height * scale))
        crop = crop.resize((new_width, new_height), Image.Resampling.LANCZOS)
    crop.save(path, format="PNG", optimize=True)
    return crop.width, crop.height, round(scale, 3)


def prepare_recognition_plan(image_path: Path, output_dir: Path) -> dict[str, Any]:
    image_path = Path(image_path).expanduser().resolve()
    output_dir = Path(output_dir).expanduser().resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    source_hash = sha256(image_path.read_bytes()).hexdigest()
    plan_id = sha256(f"{PLANNER_VERSION}:{source_hash}".encode("utf-8")).hexdigest()[:24]
    plan_path = output_dir / "recognition-plan.json"

    Image = _load_pillow()
    if Image is None:
        plan = {
            "schema": PLAN_SCHEMA,
            "planId": plan_id,
            "plannerVersion": PLANNER_VERSION,
            "sourceImage": str(image_path),
            "sourceSha256": source_hash,
            "strategy": "whole_page",
            "profile": "whole_page_fallback",
            "layoutConfidence": "fallback",
            "complexity": "unknown",
            "reason": "Pillow unavailable; use one whole-page visual transcription and human review.",
            "regions": [{
                "regionId": "whole-page",
                "kind": "whole_page",
                "path": str(image_path),
                "required": True,
                "attemptLimit": 1,
            }],
            "coverage": {"requiredRegionIds": ["whole-page"], "expectedSystems": None},
            "policy": {
                "recognitionRounds": 1,
                "maxTargetedRepairPerRegion": 1,
                "modelMayCreateCrops": False,
                "modelMaySelfRetry": False,
                "humanReviewRequired": True,
            },
        }
        plan_path.write_text(json.dumps(plan, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        return plan

    with Image.open(image_path) as source_image:
        source = source_image.convert("RGB")
        gray = source.convert("L")
        width, height = source.size
        bands = _group_ink_bands(gray)
        systems, confidence = _choose_systems(gray, bands)
        complexity = _estimate_complexity(systems)
        regularity = _regularity(systems) if systems else 0.0
        use_systems = len(systems) >= 2 and confidence in {"high", "medium"} and regularity >= 0.56
        regions: list[dict[str, Any]] = []
        if use_systems:
            profile = "system_highres_parallel" if complexity == "dense" else "system_parallel"
            first_top = systems[0].top
            if first_top >= max(58, round(height * 0.07)):
                header_bottom = max(1, first_top - max(6, round(height * 0.006)))
                header_path = output_dir / "header.png"
                header_width = 1500 if width < 1500 else width
                out_w, out_h, scale = _save_resized(source, (0, 0, width, header_bottom), header_path, header_width)
                regions.append({"regionId":"header","kind":"header","path":str(header_path),"bbox":[0,0,width,header_bottom],"outputSize":[out_w,out_h],"scale":scale,"required":False,"attemptLimit":1})
            target_width = 2200 if complexity == "dense" else 1800
            for zero_index, band in enumerate(systems):
                index = zero_index + 1
                previous_bottom = systems[zero_index - 1].bottom if zero_index > 0 else 0
                next_top = systems[zero_index + 1].top if zero_index + 1 < len(systems) else height
                available_above = max(0, band.top - previous_bottom)
                available_below = max(0, next_top - band.bottom)
                desired_pad = max(14, round(band.height * (0.26 if complexity == "dense" else 0.22)))
                pad_top = min(desired_pad, max(6, available_above // 2))
                pad_bottom = min(desired_pad, max(6, available_below // 2))
                top = max(0, band.top - pad_top)
                bottom = min(height, band.bottom + pad_bottom)
                crop_path = output_dir / f"system-{index:02d}.png"
                out_w, out_h, scale = _save_resized(source, (0, top, width, bottom), crop_path, target_width)
                barline_candidates = _soft_barline_candidates(gray, band)
                regions.append({
                    "regionId": f"system-{index:02d}", "kind": "system", "systemIndex": index,
                    "path": str(crop_path), "bbox": [0, top, width, bottom], "outputSize": [out_w, out_h],
                    "scale": scale, "required": True, "attemptLimit": 2,
                    "barlineHint": len(barline_candidates) or None,
                    "barlineCandidatesSourceX": barline_candidates,
                    "barlineCandidatesNormalized": [round(x / max(1, width), 4) for x in barline_candidates],
                    "measureBoundaryPolicy": "visible_barlines_first_duration_never_splits",
                })
            strategy = "music_systems"
        else:
            profile = "whole_page_fast"
            whole_path = output_dir / "whole-page.png"
            target_width = 1800 if width < 1400 else width
            out_w, out_h, scale = _save_resized(source, (0, 0, width, height), whole_path, target_width)
            regions.append({"regionId":"whole-page","kind":"whole_page","path":str(whole_path),"bbox":[0,0,width,height],"outputSize":[out_w,out_h],"scale":scale,"required":True,"attemptLimit":1})
            strategy = "whole_page"
        required_region_ids = [item["regionId"] for item in regions if item.get("required")]
        expected_systems = len([item for item in regions if item.get("kind") == "system"]) or None
        plan = {
            "schema": PLAN_SCHEMA, "planId": plan_id, "plannerVersion": PLANNER_VERSION,
            "sourceImage": str(image_path), "sourceSha256": source_hash,
            "image": {"width": width, "height": height}, "strategy": strategy, "profile": profile,
            "layoutConfidence": confidence if use_systems else "fallback", "complexity": complexity,
            "systemRegularity": round(regularity, 3), "regions": regions,
            "coverage": {"requiredRegionIds": required_region_ids, "expectedSystems": expected_systems, "required": True},
            "policy": {
                "recognitionRounds": 1, "maxTargetedRepairPerRegion": 1,
                "modelMayCreateCrops": False, "modelMaySelfRetry": False,
                "barlineHintsAreAdvisory": True, "measureBoundarySource": "visible_barlines",
                "durationMayDefineMeasureBoundary": False, "durationChecksProveCoverage": False,
                "humanReviewRequired": True,
            },
        }
        plan_path.write_text(json.dumps(plan, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        return plan


def plan_region_map(plan: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {str(item.get("regionId")): item for item in plan.get("regions") or [] if isinstance(item, dict) and item.get("regionId")}


def compatibility_layout_manifest(plan: dict[str, Any]) -> dict[str, Any]:
    systems = []
    header = None
    for item in plan.get("regions") or []:
        if item.get("kind") == "header":
            header = {key: item.get(key) for key in ("path", "bbox", "scale") if item.get(key) is not None}
        elif item.get("kind") == "system":
            systems.append({
                "systemIndex": item.get("systemIndex"), "path": item.get("path"), "bbox": item.get("bbox"),
                "scale": item.get("scale"), "barlineHint": item.get("barlineHint"),
                "barlineCandidatesSourceX": item.get("barlineCandidatesSourceX"),
                "barlineCandidatesNormalized": item.get("barlineCandidatesNormalized"),
                "measureBoundaryPolicy": item.get("measureBoundaryPolicy"),
            })
    return {
        "schema": "animal-band-score-layout-v1", "manifestId": plan.get("planId"),
        "analyzerVersion": plan.get("plannerVersion"), "sourceImage": plan.get("sourceImage"),
        "sourceSha256": plan.get("sourceSha256"), "image": plan.get("image"), "strategy": plan.get("strategy"),
        "layoutConfidence": plan.get("layoutConfidence"), "complexity": plan.get("complexity"),
        "systemRegularity": plan.get("systemRegularity"), "header": header, "systems": systems,
        "sourceCoverage": {"expectedSystems": (plan.get("coverage") or {}).get("expectedSystems"), "required": bool((plan.get("coverage") or {}).get("required"))},
        "policy": plan.get("policy"),
    }
