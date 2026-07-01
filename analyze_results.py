#!/usr/bin/env python3
"""
Universe Search Research Analyzer

Reads Universe Search result folders and generates human-readable research reports.
Works with both older generation_*.json outputs and newer Atlas-based outputs.

Usage:
    python analyze_results.py
    python analyze_results.py universe_search_v20_results
    python analyze_results.py universe_search_v20_results --out reports
"""

from __future__ import annotations

import argparse
import json
import math
import statistics
import time
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

NUMERIC_METRICS = [
    "score",
    "active",
    "edge",
    "boundary_activity",
    "islands",
    "nested_score_raw",
    "ms_local_life",
    "ms_flow",
    "ms_rotation_flow",
    "persistent_tracks",
    "entity_count",
    "best_entity_quality",
    "best_region_score",
    "region_count",
    "novelty_behavior",
    "in_generation_diversity",
    "macro_scaffold",
    "memory_trace_score",
    "cosmic_recovery",
    "crystal_order",
    "crystal_error",
    "defect_density",
    "defect_density_var",
    "defect_persistence",
    "defect_motion",
    "defect_density_window",
    "quasi_particle_score",
    "crystal_defect_bonus",
    "observer_score",
    "post_test_truth",
    "degeneracy_penalty",
    "degeneracy_penalty_raw",
]

CORE_METRICS = [
    "score",
    "ms_local_life",
    "memory_trace_score",
    "persistent_tracks",
    "best_entity_quality",
    "best_region_score",
    "ms_flow",
    "ms_rotation_flow",
    "cosmic_recovery",
    "crystal_order",
    "defect_density",
    "defect_persistence",
    "defect_motion",
    "quasi_particle_score",
    "novelty_behavior",
    "in_generation_diversity",
]

CORRELATION_METRICS = [
    "score",
    "ms_local_life",
    "memory_trace_score",
    "persistent_tracks",
    "best_entity_quality",
    "best_region_score",
    "ms_flow",
    "ms_rotation_flow",
    "cosmic_recovery",
    "crystal_order",
    "defect_density",
    "defect_density_window",
    "defect_persistence",
    "defect_motion",
    "quasi_particle_score",
    "active",
    "edge",
    "macro_scaffold",
]


def safe_float(value: Any) -> Optional[float]:
    if value is None or isinstance(value, bool):
        return None
    try:
        x = float(value)
    except (TypeError, ValueError):
        return None
    if math.isnan(x) or math.isinf(x):
        return None
    return x


def fmt_num(value: Any, digits: int = 3) -> str:
    x = safe_float(value)
    if x is None:
        return "n/a"
    if abs(x) >= 1000:
        return f"{x:,.1f}"
    return f"{x:.{digits}f}"


def load_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def classify_from_metrics(m: Dict[str, Any]) -> str:
    if m.get("eval_error"):
        return "Execution Failed Scaffold"

    active = safe_float(m.get("active")) or 0.0
    edge = safe_float(m.get("edge")) or 0.0
    life = safe_float(m.get("ms_local_life")) or 0.0
    flow = safe_float(m.get("ms_flow")) or 0.0
    rot = safe_float(m.get("ms_rotation_flow")) or 0.0
    mem = max(0.0, safe_float(m.get("memory_trace_score")) or 0.0) / 120.0
    tracks = safe_float(m.get("persistent_tracks")) or 0.0
    ent_q = safe_float(m.get("best_entity_quality")) or 0.0
    reg = safe_float(m.get("best_region_score")) or 0.0
    cr = safe_float(m.get("cosmic_recovery")) or 0.0
    nested = safe_float(m.get("nested_score_raw")) or 0.0
    qps = safe_float(m.get("quasi_particle_score")) or 0.0
    xtal = safe_float(m.get("crystal_order")) or 0.0
    dd = safe_float(m.get("defect_density")) or 0.0

    if active > 0.96 and edge < 0.04:
        return "Degenerate Smooth Soup"
    if active < 0.02:
        return "Dead Empty Field"
    if tracks >= 30 and ent_q >= 0.65 and life >= 0.55:
        if mem >= 0.55:
            return "Entity Memory Ecology"
        return "Persistent Entity Garden"
    if flow > 0.08 and rot > 0.06 and life >= 0.55:
        return "Rotating Flow World"
    if flow > 0.08 and life >= 0.50:
        return "Flow World"
    if mem >= 0.60 and cr >= 0.45:
        return "Recovery Memory World"
    if reg >= 0.45 and nested >= 0.55:
        return "Living Boundary Region"
    if nested >= 0.60 and life >= 0.50:
        return "Nested Local Life"
    if qps >= 0.42 and xtal >= 0.55:
        return "Crystal Defect Ecology"
    if xtal >= 0.72 and 0.005 <= dd <= 0.22:
        return "Almost Crystal With Defects"
    if xtal >= 0.78 and dd < 0.005:
        return "Clean Crystal"
    if cr >= 0.65:
        return "Resilient Scaffold"
    return "Weird Unknown"


def world_description(m: Dict[str, Any]) -> List[str]:
    notes: List[str] = []

    score = safe_float(m.get("score")) or 0.0
    life = safe_float(m.get("ms_local_life")) or 0.0
    memory = safe_float(m.get("memory_trace_score")) or 0.0
    tracks = safe_float(m.get("persistent_tracks")) or 0.0
    flow = safe_float(m.get("ms_flow")) or 0.0
    rot = safe_float(m.get("ms_rotation_flow")) or 0.0
    recovery = safe_float(m.get("cosmic_recovery")) or 0.0
    region = safe_float(m.get("best_region_score")) or 0.0
    ent_q = safe_float(m.get("best_entity_quality")) or 0.0
    xtal = safe_float(m.get("crystal_order")) or 0.0
    defect = safe_float(m.get("defect_density")) or 0.0
    persist = safe_float(m.get("defect_persistence")) or 0.0
    motion = safe_float(m.get("defect_motion")) or 0.0
    qps = safe_float(m.get("quasi_particle_score")) or 0.0

    if score >= 220:
        notes.append("very high overall score")
    if life >= 0.60:
        notes.append("strong local-life signal")
    if memory >= 70:
        notes.append("high memory trace")
    elif memory >= 40:
        notes.append("moderate memory trace")
    if tracks >= 30:
        notes.append("many persistent tracks")
    if ent_q >= 0.65:
        notes.append("high-quality entity-like structures")
    if region >= 0.45:
        notes.append("strong region-level organization")
    if flow >= 0.08 and rot >= 0.06:
        notes.append("rotating flow dynamics")
    elif flow >= 0.08:
        notes.append("clear flow dynamics")
    if recovery >= 0.55:
        notes.append("strong recovery after perturbation")
    if xtal >= 0.72 and 0.005 <= defect <= 0.22:
        notes.append("crystal-like scaffold with non-trivial defects")
    elif xtal >= 0.78:
        notes.append("very clean crystal-like order")
    if qps >= 0.42:
        notes.append("possible quasi-particle / defect ecology")
    if persist >= 0.35 and motion >= 0.05:
        notes.append("defects show both persistence and motion")
    if not notes:
        notes.append("interesting mainly by combined score and observer evaluation")
    return notes


def collect_generation_worlds(results_dir: Path) -> List[Dict[str, Any]]:
    worlds: List[Dict[str, Any]] = []
    for path in sorted(results_dir.glob("generation_*.json")):
        try:
            data = load_json(path)
        except Exception as e:
            print(f"Warning: could not read {path}: {e}")
            continue
        if not isinstance(data, list):
            continue
        gen = parse_generation_number(path.name)
        for rank, item in enumerate(data, 1):
            if not isinstance(item, dict):
                continue
            metrics = dict(item.get("metrics") or {})
            score = safe_float(item.get("score"))
            if score is None:
                score = safe_float(metrics.get("score"))
            metrics["score"] = score if score is not None else 0.0
            rule = item.get("rule") or {}
            rule_id = rule.get("rule_id", metrics.get("rule_id", "unknown")) if isinstance(rule, dict) else metrics.get("rule_id", "unknown")
            klass = metrics.get("class") or classify_from_metrics(metrics)
            worlds.append({
                "source": "generation",
                "generation": gen,
                "rank": rank,
                "rule_id": rule_id,
                "score": metrics["score"],
                "class": klass,
                "metrics": metrics,
                "rule": rule,
                "path": str(path),
            })
    return worlds


def parse_generation_number(filename: str) -> Optional[int]:
    # generation_01_observer_niches.json -> 1
    parts = filename.split("_")
    if len(parts) >= 2:
        try:
            return int(parts[1])
        except ValueError:
            return None
    return None


def collect_atlas_worlds(results_dir: Path) -> List[Dict[str, Any]]:
    index_path = results_dir / "atlas" / "atlas_index.json"
    if not index_path.exists():
        return []
    try:
        data = load_json(index_path)
    except Exception as e:
        print(f"Warning: could not read atlas index: {e}")
        return []
    if not isinstance(data, list):
        return []

    worlds: List[Dict[str, Any]] = []
    for rank, item in enumerate(data, 1):
        if not isinstance(item, dict):
            continue
        metrics: Dict[str, Any] = {}
        folder = item.get("folder")
        if folder:
            metrics_path = Path(folder) / "metrics.json"
            if not metrics_path.is_absolute():
                metrics_path = Path.cwd() / metrics_path
            if not metrics_path.exists():
                # Try relative to results_dir parent / project folder.
                metrics_path = results_dir.parent / folder / "metrics.json"
            if metrics_path.exists():
                try:
                    loaded = load_json(metrics_path)
                    if isinstance(loaded, dict):
                        metrics.update(loaded)
                except Exception:
                    pass
        metrics.update({k: v for k, v in item.items() if k not in ("folder", "preview", "preview_gif")})
        score = safe_float(item.get("score")) or safe_float(metrics.get("score")) or 0.0
        metrics["score"] = score
        worlds.append({
            "source": "atlas",
            "generation": item.get("generation"),
            "rank": rank,
            "rule_id": item.get("rule_id", "unknown"),
            "score": score,
            "class": item.get("class") or classify_from_metrics(metrics),
            "metrics": metrics,
            "rule": {},
            "folder": item.get("folder"),
            "preview": item.get("preview"),
            "preview_gif": item.get("preview_gif"),
        })
    return worlds


def dedupe_worlds(worlds: Iterable[Dict[str, Any]]) -> List[Dict[str, Any]]:
    best: Dict[str, Dict[str, Any]] = {}
    for w in worlds:
        rid = str(w.get("rule_id", "unknown"))
        gen = str(w.get("generation", "?"))
        key = f"{rid}:{gen}:{w.get('source')}"
        # Atlas entries may represent the same rule across generations. For global stats generation entries are better.
        score = safe_float(w.get("score")) or 0.0
        if key not in best or score > (safe_float(best[key].get("score")) or -1e18):
            best[key] = w
    return list(best.values())


def metric_values(worlds: Sequence[Dict[str, Any]], metric: str) -> List[float]:
    vals: List[float] = []
    for w in worlds:
        if metric == "score":
            x = safe_float(w.get("score"))
        else:
            x = safe_float(w.get("metrics", {}).get(metric))
        if x is not None:
            vals.append(x)
    return vals


def metric_summary(worlds: Sequence[Dict[str, Any]], metric: str) -> Optional[Dict[str, float]]:
    vals = metric_values(worlds, metric)
    if not vals:
        return None
    vals_sorted = sorted(vals)
    return {
        "count": float(len(vals)),
        "min": vals_sorted[0],
        "max": vals_sorted[-1],
        "mean": statistics.fmean(vals),
        "median": statistics.median(vals_sorted),
        "stdev": statistics.pstdev(vals) if len(vals) > 1 else 0.0,
    }


def pearson(xs: Sequence[float], ys: Sequence[float]) -> Optional[float]:
    n = min(len(xs), len(ys))
    if n < 4:
        return None
    xs = xs[:n]
    ys = ys[:n]
    mx = statistics.fmean(xs)
    my = statistics.fmean(ys)
    vx = sum((x - mx) ** 2 for x in xs)
    vy = sum((y - my) ** 2 for y in ys)
    if vx <= 1e-12 or vy <= 1e-12:
        return None
    cov = sum((x - mx) * (y - my) for x, y in zip(xs, ys))
    return cov / math.sqrt(vx * vy)


def correlations(worlds: Sequence[Dict[str, Any]]) -> List[Tuple[str, str, float, int]]:
    rows: List[Tuple[str, str, float, int]] = []
    for i, a in enumerate(CORRELATION_METRICS):
        for b in CORRELATION_METRICS[i + 1:]:
            xs: List[float] = []
            ys: List[float] = []
            for w in worlds:
                ma = safe_float(w.get("score") if a == "score" else w.get("metrics", {}).get(a))
                mb = safe_float(w.get("score") if b == "score" else w.get("metrics", {}).get(b))
                if ma is not None and mb is not None:
                    xs.append(ma)
                    ys.append(mb)
            r = pearson(xs, ys)
            if r is not None:
                rows.append((a, b, r, len(xs)))
    rows.sort(key=lambda row: abs(row[2]), reverse=True)
    return rows


def zscore_outliers(worlds: Sequence[Dict[str, Any]], metrics: Sequence[str], limit: int = 15) -> List[Dict[str, Any]]:
    stats: Dict[str, Tuple[float, float]] = {}
    for m in metrics:
        vals = metric_values(worlds, m)
        if len(vals) >= 5:
            mean = statistics.fmean(vals)
            sd = statistics.pstdev(vals)
            if sd > 1e-12:
                stats[m] = (mean, sd)

    out: List[Dict[str, Any]] = []
    for w in worlds:
        reasons: List[Tuple[str, float, float]] = []
        for m, (mean, sd) in stats.items():
            value = safe_float(w.get("score") if m == "score" else w.get("metrics", {}).get(m))
            if value is None:
                continue
            z = (value - mean) / sd
            if abs(z) >= 2.0:
                reasons.append((m, value, z))
        if reasons:
            reasons.sort(key=lambda x: abs(x[2]), reverse=True)
            out.append({"world": w, "reasons": reasons[:4], "strength": max(abs(r[2]) for r in reasons)})
    out.sort(key=lambda x: x["strength"], reverse=True)
    return out[:limit]


def make_markdown_table(headers: Sequence[str], rows: Sequence[Sequence[Any]]) -> str:
    if not rows:
        return "_No data._\n"
    lines = ["| " + " | ".join(headers) + " |", "| " + " | ".join(["---"] * len(headers)) + " |"]
    for row in rows:
        lines.append("| " + " | ".join(str(x) for x in row) + " |")
    return "\n".join(lines) + "\n"


def top_worlds(worlds: Sequence[Dict[str, Any]], limit: int = 15) -> List[Dict[str, Any]]:
    return sorted(worlds, key=lambda w: safe_float(w.get("score")) or -1e18, reverse=True)[:limit]


def top_by_metric(worlds: Sequence[Dict[str, Any]], metric: str, limit: int = 10) -> List[Dict[str, Any]]:
    return sorted(worlds, key=lambda w: safe_float(w.get("score") if metric == "score" else w.get("metrics", {}).get(metric)) or -1e18, reverse=True)[:limit]


def world_label(w: Dict[str, Any]) -> str:
    rid = w.get("rule_id", "unknown")
    gen = w.get("generation")
    if gen is None:
        return f"rule {rid}"
    return f"rule {rid} / gen {gen}"


def generate_summary(results_dir: Path, out_dir: Path) -> Tuple[Dict[str, Any], Dict[str, str]]:
    generation_worlds = collect_generation_worlds(results_dir)
    atlas_worlds = collect_atlas_worlds(results_dir)

    # Use generation worlds for most statistics to avoid atlas selection bias.
    stat_worlds = generation_worlds if generation_worlds else atlas_worlds
    all_worlds = dedupe_worlds(generation_worlds + atlas_worlds)

    class_counts = Counter(w.get("class", "Unknown") for w in stat_worlds)
    gen_counts = Counter(w.get("generation") for w in generation_worlds if w.get("generation") is not None)
    source_counts = Counter(w.get("source") for w in all_worlds)
    metric_stats = {m: metric_summary(stat_worlds, m) for m in CORE_METRICS}
    metric_stats = {k: v for k, v in metric_stats.items() if v is not None}
    corr_rows = correlations(stat_worlds)
    outlier_rows = zscore_outliers(stat_worlds, CORE_METRICS, limit=20)
    best = top_worlds(stat_worlds, limit=20)

    report_data: Dict[str, Any] = {
        "created_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "results_dir": str(results_dir),
        "total_generation_worlds": len(generation_worlds),
        "total_atlas_worlds": len(atlas_worlds),
        "total_unique_records": len(all_worlds),
        "generation_counts": dict(sorted(gen_counts.items())),
        "source_counts": dict(source_counts),
        "class_counts": dict(class_counts.most_common()),
        "metric_summary": metric_stats,
        "top_correlations": [
            {"a": a, "b": b, "r": r, "n": n} for a, b, r, n in corr_rows[:30]
        ],
        "top_worlds": [compact_world(w) for w in best[:20]],
        "outliers": [compact_outlier(o) for o in outlier_rows[:20]],
    }

    reports = {
        "research_summary.md": build_research_summary(report_data, stat_worlds, atlas_worlds, corr_rows, outlier_rows),
        "interesting_worlds.md": build_interesting_worlds(stat_worlds, atlas_worlds),
        "correlations.md": build_correlations_report(stat_worlds, corr_rows),
        "next_experiments.md": build_next_experiments(report_data, stat_worlds, corr_rows, outlier_rows),
    }
    return report_data, reports


def compact_world(w: Dict[str, Any]) -> Dict[str, Any]:
    m = w.get("metrics", {})
    return {
        "label": world_label(w),
        "rule_id": w.get("rule_id"),
        "generation": w.get("generation"),
        "score": safe_float(w.get("score")) or 0.0,
        "class": w.get("class"),
        "metrics": {k: m.get(k) for k in CORE_METRICS if k in m},
    }


def compact_outlier(o: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "world": compact_world(o["world"]),
        "reasons": [{"metric": m, "value": value, "z": z} for m, value, z in o["reasons"]],
    }


def build_research_summary(data: Dict[str, Any], worlds: Sequence[Dict[str, Any]], atlas_worlds: Sequence[Dict[str, Any]], corr_rows: Sequence[Tuple[str, str, float, int]], outliers: Sequence[Dict[str, Any]]) -> str:
    lines: List[str] = []
    lines.append("# Universe Search Research Report")
    lines.append("")
    lines.append(f"Created: **{data['created_at']}**")
    lines.append(f"Results folder: `{data['results_dir']}`")
    lines.append("")
    lines.append("## Executive Summary")
    lines.append("")
    lines.append(f"- Generation world records analyzed: **{data['total_generation_worlds']}**")
    lines.append(f"- Atlas entries found: **{data['total_atlas_worlds']}**")
    lines.append(f"- Unique records loaded: **{data['total_unique_records']}**")
    if data["generation_counts"]:
        gens = sorted(int(g) for g in data["generation_counts"].keys())
        lines.append(f"- Generations present: **{min(gens)} to {max(gens)}**")
    lines.append("")

    lines.append("## Most Common World Families")
    lines.append("")
    class_rows = []
    total = max(1, sum(data["class_counts"].values()))
    for klass, count in list(data["class_counts"].items())[:15]:
        class_rows.append([klass, count, f"{100.0 * count / total:.1f}%"])
    lines.append(make_markdown_table(["Class", "Count", "Share"], class_rows))

    lines.append("## Top Discoveries by Score")
    lines.append("")
    top_rows = []
    for w in top_worlds(worlds, 12):
        m = w.get("metrics", {})
        top_rows.append([
            world_label(w),
            fmt_num(w.get("score")),
            w.get("class"),
            fmt_num(m.get("memory_trace_score"), 1),
            fmt_num(m.get("persistent_tracks"), 0),
            fmt_num(m.get("quasi_particle_score")),
        ])
    lines.append(make_markdown_table(["World", "Score", "Class", "Memory", "Tracks", "Quasi"], top_rows))

    lines.append("## Core Metric Summary")
    lines.append("")
    metric_rows = []
    for metric, s in data["metric_summary"].items():
        metric_rows.append([metric, fmt_num(s["mean"]), fmt_num(s["median"]), fmt_num(s["max"]), fmt_num(s["stdev"])])
    lines.append(make_markdown_table(["Metric", "Mean", "Median", "Max", "Std"], metric_rows))

    lines.append("## Strongest Correlations")
    lines.append("")
    corr_table = []
    for a, b, r, n in corr_rows[:15]:
        corr_table.append([a, b, f"{r:+.3f}", n])
    lines.append(make_markdown_table(["Metric A", "Metric B", "Pearson r", "N"], corr_table))

    lines.append("## Interesting Outliers")
    lines.append("")
    if outliers:
        for o in outliers[:10]:
            w = o["world"]
            lines.append(f"### {world_label(w)}")
            lines.append("")
            lines.append(f"- Class: **{w.get('class')}**")
            lines.append(f"- Score: **{fmt_num(w.get('score'))}**")
            reason_text = "; ".join(f"`{m}`={fmt_num(value)} (z={z:+.2f})" for m, value, z in o["reasons"])
            lines.append(f"- Outlier signals: {reason_text}")
            lines.append("")
    else:
        lines.append("_No strong outliers detected._")
        lines.append("")

    lines.append("## Open Questions")
    lines.append("")
    for q in infer_open_questions(data, corr_rows):
        lines.append(f"- {q}")
    lines.append("")
    lines.append("## Files Generated")
    lines.append("")
    lines.append("- `research_summary.md` — this overview")
    lines.append("- `research_summary.json` — machine-readable summary")
    lines.append("- `interesting_worlds.md` — detailed cards for worlds worth viewing")
    lines.append("- `correlations.md` — correlation analysis")
    lines.append("- `next_experiments.md` — suggested follow-up experiments")
    lines.append("")
    return "\n".join(lines)


def build_interesting_worlds(worlds: Sequence[Dict[str, Any]], atlas_worlds: Sequence[Dict[str, Any]]) -> str:
    lines = ["# Interesting Worlds", ""]
    selected: Dict[str, Dict[str, Any]] = {}
    for w in top_worlds(worlds, 15):
        selected[world_label(w)] = w
    for metric in ["memory_trace_score", "persistent_tracks", "quasi_particle_score", "crystal_order", "defect_motion", "ms_flow", "cosmic_recovery"]:
        for w in top_by_metric(worlds, metric, 5):
            selected[world_label(w)] = w
    for w in atlas_worlds[:20]:
        selected[world_label(w)] = w

    ranked = sorted(selected.values(), key=lambda w: safe_float(w.get("score")) or -1e18, reverse=True)
    for w in ranked[:40]:
        m = w.get("metrics", {})
        lines.append(f"## {world_label(w)}")
        lines.append("")
        lines.append(f"- Class: **{w.get('class')}**")
        lines.append(f"- Score: **{fmt_num(w.get('score'))}**")
        if w.get("folder"):
            lines.append(f"- Atlas folder: `{w.get('folder')}`")
        if w.get("preview_gif"):
            lines.append(f"- Preview GIF: `{w.get('preview_gif')}`")
        elif w.get("preview"):
            lines.append(f"- Preview image: `{w.get('preview')}`")
        lines.append("- Why interesting: " + ", ".join(world_description(m)) + ".")
        lines.append("")
        metric_rows = []
        for metric in CORE_METRICS:
            if metric == "score":
                value = w.get("score")
            else:
                value = m.get(metric)
            if value is not None:
                metric_rows.append([metric, fmt_num(value)])
        lines.append(make_markdown_table(["Metric", "Value"], metric_rows))
        note = m.get("observer_note")
        if note:
            lines.append(f"Observer note: {note}")
            lines.append("")
    return "\n".join(lines)


def build_correlations_report(worlds: Sequence[Dict[str, Any]], corr_rows: Sequence[Tuple[str, str, float, int]]) -> str:
    lines = ["# Correlation Analysis", ""]
    lines.append("Pearson correlations are calculated from available numeric metrics across generation result files.")
    lines.append("Correlation is not causation. Treat these as pattern hints, not proof.")
    lines.append("")
    table = []
    for a, b, r, n in corr_rows[:50]:
        direction = "positive" if r > 0 else "negative"
        table.append([a, b, f"{r:+.3f}", direction, n])
    lines.append(make_markdown_table(["Metric A", "Metric B", "r", "Direction", "N"], table))
    lines.append("")
    lines.append("## Metric Leaders")
    lines.append("")
    for metric in ["score", "memory_trace_score", "persistent_tracks", "quasi_particle_score", "crystal_order", "defect_motion", "ms_flow", "cosmic_recovery"]:
        lines.append(f"### Top by `{metric}`")
        lines.append("")
        rows = []
        for w in top_by_metric(worlds, metric, 8):
            value = w.get("score") if metric == "score" else w.get("metrics", {}).get(metric)
            rows.append([world_label(w), fmt_num(value), fmt_num(w.get("score")), w.get("class")])
        lines.append(make_markdown_table(["World", metric, "Score", "Class"], rows))
        lines.append("")
    return "\n".join(lines)


def build_next_experiments(data: Dict[str, Any], worlds: Sequence[Dict[str, Any]], corr_rows: Sequence[Tuple[str, str, float, int]], outliers: Sequence[Dict[str, Any]]) -> str:
    lines = ["# Suggested Next Experiments", ""]
    lines.append("These suggestions are heuristic. Use them as prompts for the next run, not as conclusions.")
    lines.append("")

    class_counts = data.get("class_counts", {})
    top_classes = list(class_counts.keys())[:5]
    lines.append("## What this run seems to emphasize")
    lines.append("")
    if top_classes:
        lines.append("Most common classes: " + ", ".join(f"**{c}**" for c in top_classes) + ".")
    else:
        lines.append("Not enough class data.")
    lines.append("")

    lines.append("## Candidate experiments")
    lines.append("")
    suggestions = infer_experiments(data, corr_rows, outliers)
    for i, s in enumerate(suggestions, 1):
        lines.append(f"### {i}. {s['title']}")
        lines.append("")
        lines.append(s["body"])
        lines.append("")
        if s.get("watch"):
            lines.append("Watch metrics: " + ", ".join(f"`{x}`" for x in s["watch"]) + ".")
            lines.append("")

    lines.append("## Manual viewing shortlist")
    lines.append("")
    rows = []
    for w in top_worlds(worlds, 10):
        rows.append([world_label(w), fmt_num(w.get("score")), w.get("class"), ", ".join(world_description(w.get("metrics", {}))[:3])])
    lines.append(make_markdown_table(["World", "Score", "Class", "Reason"], rows))
    return "\n".join(lines)


def infer_open_questions(data: Dict[str, Any], corr_rows: Sequence[Tuple[str, str, float, int]]) -> List[str]:
    questions = []
    pairs = {(a, b): r for a, b, r, _ in corr_rows[:40]}
    flat = [(a, b, r) for a, b, r, _ in corr_rows[:40]]

    def has_pair(x: str, y: str, threshold: float = 0.35) -> Optional[float]:
        for a, b, r in flat:
            if {a, b} == {x, y} and abs(r) >= threshold:
                return r
        return None

    r = has_pair("memory_trace_score", "defect_density")
    if r is not None:
        questions.append(f"Is memory linked to defect density? Observed correlation r={r:+.2f}.")
    r = has_pair("memory_trace_score", "persistent_tracks")
    if r is not None:
        questions.append(f"Do persistent tracks act as a substrate for memory? Observed correlation r={r:+.2f}.")
    r = has_pair("crystal_order", "quasi_particle_score")
    if r is not None:
        questions.append(f"Do crystal-like scaffolds support quasi-particle behavior? Observed correlation r={r:+.2f}.")
    r = has_pair("ms_flow", "ms_rotation_flow")
    if r is not None:
        questions.append(f"Are flow worlds mostly rotating-flow worlds? Observed correlation r={r:+.2f}.")

    class_counts = data.get("class_counts", {})
    if class_counts:
        most_common = next(iter(class_counts.keys()))
        questions.append(f"Why did `{most_common}` dominate this run, and is that a property of the search objective or the rule space?")
    questions.append("Which top worlds remain visually interesting when inspected outside the scoring metrics?")
    questions.append("Does the Atlas contain genuinely different families, or many variants of the same behavior?")
    return questions


def infer_experiments(data: Dict[str, Any], corr_rows: Sequence[Tuple[str, str, float, int]], outliers: Sequence[Dict[str, Any]]) -> List[Dict[str, Any]]:
    suggestions: List[Dict[str, Any]] = []
    top_corr = corr_rows[:15]
    has_crystal_signal = any({a, b} & {"crystal_order", "defect_density", "quasi_particle_score"} for a, b, _, _ in top_corr)
    has_memory_signal = any({a, b} & {"memory_trace_score", "persistent_tracks"} for a, b, _, _ in top_corr)

    if has_crystal_signal:
        suggestions.append({
            "title": "Crystal-defect focused run",
            "body": "Run a variant that slightly increases the weight of `quasi_particle_score` and tracks whether crystal-defect worlds become more common or merely overfit the score.",
            "watch": ["crystal_order", "defect_density", "defect_persistence", "defect_motion", "quasi_particle_score"],
        })
    else:
        suggestions.append({
            "title": "Probe crystal-defect rarity",
            "body": "Crystal metrics did not dominate the strongest correlations. Run a smaller experiment with a stronger crystal-defect bonus to see whether these worlds are rare or merely under-selected.",
            "watch": ["crystal_order", "defect_density", "quasi_particle_score"],
        })

    if has_memory_signal:
        suggestions.append({
            "title": "Memory lineage run",
            "body": "Top correlations suggest memory or tracks may be meaningful. Seed a run with the best memory-rich worlds and watch whether memory survives across generations.",
            "watch": ["memory_trace_score", "persistent_tracks", "best_entity_quality", "cosmic_recovery"],
        })

    if outliers:
        w = outliers[0]["world"]
        suggestions.append({
            "title": f"Neighborhood search around {world_label(w)}",
            "body": "The strongest outlier may represent a rare behavior. Use its rule as a human favorite seed or mutation center and test whether nearby rules preserve the same behavior.",
            "watch": ["score", "novelty_behavior", "in_generation_diversity"],
        })

    suggestions.append({
        "title": "Control run without crystal bonus",
        "body": "To check whether crystal-related discoveries are caused by the new objective, run a control version with `CRYSTAL_DEFECT_BONUS = 0.0` and compare class distribution, best scores and Atlas diversity.",
        "watch": ["class distribution", "score", "quasi_particle_score", "diversity skeleton size"],
    })
    suggestions.append({
        "title": "Atlas diversity audit",
        "body": "Manually inspect the top Atlas entries and mark which worlds are visually distinct. This tests whether numeric novelty corresponds to human-visible novelty.",
        "watch": ["class", "preview_gif", "observer_note"],
    })
    return suggestions[:6]


def write_outputs(out_dir: Path, report_data: Dict[str, Any], reports: Dict[str, str]) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    for filename, text in reports.items():
        (out_dir / filename).write_text(text, encoding="utf-8")
    (out_dir / "research_summary.json").write_text(json.dumps(report_data, indent=2, ensure_ascii=False), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate research reports from Universe Search results.")
    parser.add_argument("results_dir", nargs="?", default="universe_search_v20_results", help="Path to results folder. Default: universe_search_v20_results")
    parser.add_argument("--out", default=None, help="Output folder. Default: <results_dir>/research_report")
    args = parser.parse_args()

    results_dir = Path(args.results_dir)
    if not results_dir.exists():
        raise SystemExit(f"Results folder not found: {results_dir}")

    out_dir = Path(args.out) if args.out else results_dir / "research_report"
    report_data, reports = generate_summary(results_dir, out_dir)
    write_outputs(out_dir, report_data, reports)

    print("Universe Search Research Analyzer")
    print("=" * 42)
    print(f"Results folder : {results_dir}")
    print(f"Output folder  : {out_dir}")
    print(f"World records  : {report_data['total_generation_worlds']}")
    print(f"Atlas entries  : {report_data['total_atlas_worlds']}")
    print("Generated files:")
    for name in ["research_summary.md", "research_summary.json", "interesting_worlds.md", "correlations.md", "next_experiments.md"]:
        print(f"  - {out_dir / name}")


if __name__ == "__main__":
    main()
