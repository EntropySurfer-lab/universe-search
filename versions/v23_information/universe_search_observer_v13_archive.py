#!/usr/bin/env python3
"""
Universe Search Observer v1.3 Observation Archive

Standalone life observer/viewer for Universe Search.

New in v1.2:
- Writes live samples CSV while the world is running.
- Computes organism "health" = largest_object / peak_largest.
- Tracks center of mass and drift speed.
- Writes a life passport JSON + Markdown summary.
- Tracks legacy / post-collapse structure.
- Estimates identity persistence and information survival.
- Still writes event CSV and observation log.

Put next to:
    universe_search.py
    universe_search_core.py

Examples:
    python universe_search_observer.py universe_search_v10_4_results 185 --log --events-csv --samples-csv --passport --auto-stop --max-ticks 100000
    python universe_search_observer.py universe_search_v20_results best --log --samples-csv --passport
"""

from __future__ import annotations

import argparse
import csv
import shutil
import json
import math
import re
from collections import deque
from datetime import datetime
from pathlib import Path

try:
    import tkinter as tk
except Exception:
    tk = None

try:
    import universe_search_core as base
except Exception as e:
    print("Could not import universe_search_core.py")
    print("Put universe_search_observer.py in the same folder as universe_search_core.py")
    print("Import error:", repr(e))
    raise


# ---------------- Loading worlds ----------------

def iter_dicts(obj):
    if isinstance(obj, dict):
        yield obj
        for value in obj.values():
            yield from iter_dicts(value)
    elif isinstance(obj, list):
        for value in obj:
            yield from iter_dicts(value)


def parse_rule_id(text):
    try:
        return int(text)
    except Exception:
        m = re.search(r"(\d+)", str(text))
        return int(m.group(1)) if m else None


def collect_world_records(results_dir: Path):
    records = []
    files = sorted(results_dir.glob("generation*.json"))
    files += sorted(results_dir.glob("best*.json"))

    atlas_dir = results_dir / "atlas"
    if atlas_dir.exists():
        files += sorted(atlas_dir.rglob("*.json"))

    for path in files:
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            continue

        for node in iter_dicts(data):
            if not isinstance(node, dict):
                continue

            rule = None
            score = None
            metrics = {}

            if isinstance(node.get("rule"), dict):
                rule = node.get("rule")
                score = node.get("score")
                if isinstance(node.get("metrics"), dict):
                    metrics = node.get("metrics")
            elif "rule_id" in node and any(k in node for k in ("weights", "thresholds", "seed", "parent_a", "parent_b")):
                rule = node

            if not isinstance(rule, dict):
                continue

            rid = rule.get("rule_id")
            if rid is None:
                continue

            gen = None
            m = re.search(r"generation[_-]?(\d+)", path.name)
            if m:
                gen = int(m.group(1))

            records.append({
                "rule_id": int(rid),
                "score": score if isinstance(score, (int, float)) else None,
                "metrics": metrics or {},
                "rule": rule,
                "source": str(path),
                "generation": gen,
                "class": metrics.get("class") or metrics.get("world_class") or metrics.get("classification"),
            })

    by_id = {}
    for rec in records:
        rid = rec["rule_id"]
        old = by_id.get(rid)
        if old is None:
            by_id[rid] = rec
            continue
        old_score = old["score"] if old["score"] is not None else -1e18
        new_score = rec["score"] if rec["score"] is not None else -1e18
        if new_score >= old_score:
            by_id[rid] = rec

    return list(by_id.values())


def choose_record(results_dir: Path, selector: str, extra: str | None = None):
    records = collect_world_records(results_dir)
    if not records:
        raise SystemExit(f"No world records found in {results_dir}")

    selector_l = str(selector).strip().lower()

    if selector_l not in ("best", "top", "outlier", "family", "list"):
        rid = parse_rule_id(selector_l)
        if rid is not None:
            for rec in records:
                if rec["rule_id"] == rid:
                    return rec
            raise SystemExit(f"Rule {rid} not found in {results_dir}")

    scored = [r for r in records if r["score"] is not None]
    scored.sort(key=lambda r: r["score"], reverse=True)

    if selector_l == "list":
        print("Top available worlds:")
        for i, r in enumerate(scored[:30], 1):
            m = r["metrics"]
            print(
                f"{i:02d}. rule {r['rule_id']:05d} "
                f"score={r['score'] if r['score'] is not None else 'n/a'} "
                f"gen={r.get('generation')} "
                f"memory={m.get('memory_trace_score')} "
                f"tracks={m.get('persistent_tracks')} "
                f"flow={m.get('ms_flow')} "
                f"rotation={m.get('ms_rotation_flow')} "
                f"crystal={m.get('crystal_order')} "
                f"quasi={m.get('quasi_particle_score')}"
            )
        raise SystemExit(0)

    if selector_l == "best":
        return scored[0] if scored else records[0]

    if selector_l == "top":
        n = max(1, int(extra or "1"))
        return scored[min(n - 1, len(scored) - 1)] if scored else records[0]

    if selector_l == "family":
        fam = (extra or "").lower().strip()
        if not fam:
            raise SystemExit('Family name required, e.g. family "Entity Memory Ecology"')
        matches = []
        for r in records:
            klass = str(r.get("class") or r["metrics"].get("class") or "")
            if fam in klass.lower():
                matches.append(r)
        if not matches:
            raise SystemExit(f"No records found for family: {extra}")
        matches.sort(key=lambda r: r["score"] if r["score"] is not None else -1e18, reverse=True)
        return matches[0]

    if selector_l == "outlier":
        md = results_dir / "research_report" / "research_summary.md"
        if md.exists():
            text = md.read_text(encoding="utf-8", errors="ignore")
            m = re.search(r"### rule\s+(\d+)", text, flags=re.I)
            if m:
                rid = int(m.group(1))
                for r in records:
                    if r["rule_id"] == rid:
                        return r

        def weird(r):
            m = r["metrics"]
            return (
                float(m.get("ms_flow", 0) or 0) * 4
                + float(m.get("ms_rotation_flow", 0) or 0) * 4
                + float(m.get("defect_motion", 0) or 0) * 2
                + float(m.get("quasi_particle_score", 0) or 0)
            )
        return max(records, key=weird)

    raise SystemExit(f"Unknown selector: {selector}")


# ---------------- Visuals ----------------

def rgb_hex(a: float):
    a = max(0.0, min(1.0, float(a)))
    blue = int((1.0 - a) * 230)
    yellow = int(a * 255)
    green = int(120 + 90 * (1.0 - abs(a - 0.5) * 2))
    return f"#{yellow:02x}{green:02x}{blue:02x}"


# ---------------- Observer ----------------


# ---------------- Observation Archive v1.3 ----------------

def _next_observation_id(log_root: Path) -> int:
    nums = []
    for p in log_root.glob("observation_*"):
        m = re.match(r"observation_(\d+)", p.name)
        if m:
            nums.append(int(m.group(1)))
    return max(nums, default=0) + 1


def prepare_observation_archive(results_dir: Path, rule_label: str):
    """
    Creates a non-overwriting observation_logs/observation_XXXX + latest/observation_XXXX_rule_LABEL folder.
    Returns: (observation_dir, observation_logs/observation_XXXX + latest_root, observation_id, created_iso)
    """
    log_root = results_dir / "observation_logs/observation_XXXX + latest"
    log_root.mkdir(parents=True, exist_ok=True)

    obs_id = _next_observation_id(log_root)
    safe_label = "".join(ch if ch.isalnum() or ch in ("_", "-") else "_" for ch in str(rule_label))[:40] or "unknown"
    obs_dir = log_root / f"observation_{obs_id:04d}_rule_{safe_label}"
    obs_dir.mkdir(parents=True, exist_ok=False)

    created = datetime.now().isoformat(timespec="seconds")
    return obs_dir, log_root, obs_id, created


def finalize_observation_archive(obs_dir: Path, log_root: Path, meta: dict):
    """Writes observation.json, refreshes observation_logs/observation_XXXX + latest/latest, and appends observation_index.csv."""
    meta_path = obs_dir / "observation.json"
    meta_path.write_text(json.dumps(meta, indent=2, ensure_ascii=False), encoding="utf-8")

    latest = log_root / "latest"
    if latest.exists():
        shutil.rmtree(latest)
    latest.mkdir(parents=True, exist_ok=True)
    for item in obs_dir.iterdir():
        if item.is_file():
            shutil.copy2(item, latest / item.name)

    index_file = log_root / "observation_index.csv"
    fieldnames = [
        "observation", "created", "rule_label", "rule_id", "ticks",
        "final_stage", "longest_age", "peak_largest", "peak_defects",
        "identity_persistence", "legacy_score", "information_survival",
        "post_collapse_structure", "folder"
    ]
    exists = index_file.exists()
    with index_file.open("a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        if not exists:
            writer.writeheader()
        writer.writerow({k: meta.get(k) for k in fieldnames})

class LifeObserver:
    def __init__(
        self,
        threshold: float = 0.18,
        min_object_cells: int = 8,
        collapse_grace: int = 250,
        sample_every: int = 1,
        event_grace: int = 5,
        live_flush_every: int = 100,
        samples_path: Path | None = None,
        events_path: Path | None = None,
    ):
        self.threshold = threshold
        self.min_object_cells = min_object_cells
        self.collapse_grace = collapse_grace
        self.sample_every = max(1, sample_every)
        self.event_grace = max(1, event_grace)
        self.live_flush_every = max(1, live_flush_every)

        self.samples_path = samples_path
        self.events_path = events_path
        self._sample_file = None
        self._sample_writer = None
        self._event_file = None
        self._event_writer = None

        self.birth_tick = None
        self.last_alive_tick = None
        self.collapse_tick = None

        self.peak_cells = 0
        self.peak_objects = 0
        self.peak_largest = 0
        self.peak_tick = None
        self.longest_age = 0

        self.identity_health_sum = 0.0
        self.identity_health_samples = 0
        self.identity_persistence = 0.0
        self.post_collapse_structure = 0.0
        self.legacy_score = 0.0
        self.information_survival = 0.0
        self.expansion_front_speed = 0.0
        self.first_large_structure_tick = None
        self.first_full_field_tick = None

        self.center_start = None
        self.center_current = None
        self.center_prev = None
        self.total_drift = 0.0
        self.max_step_drift = 0.0

        self.samples = []
        self.events = []
        self.last_event = "no events yet"

        self.current = {
            "objects": 0,
            "defect_cells": 0,
            "largest": 0,
            "alive": False,
            "age": 0,
            "changed": 0,
            "health": 0.0,
            "cx": None,
            "cy": None,
            "step_drift": 0.0,
            "total_drift": 0.0,
            "legacy_score": 0.0,
            "identity_persistence": 0.0,
            "information_survival": 0.0,
            "post_collapse_structure": 0.0,
        }

        self._prev_grid = None
        self._prev_objects = None
        self._stable_objects = None
        self._stable_since = None
        self._samples_since_flush = 0

        self._open_live_files()

    def _open_live_files(self):
        if self.samples_path is not None:
            self.samples_path.parent.mkdir(parents=True, exist_ok=True)
            self._sample_file = self.samples_path.open("w", encoding="utf-8", newline="")
            self._sample_writer = csv.DictWriter(self._sample_file, fieldnames=[
                "tick", "alive", "objects", "largest", "defect_cells", "changed",
                "age", "health", "cx", "cy", "step_drift", "total_drift",
                "identity_persistence", "legacy_score", "information_survival",
                "post_collapse_structure", "expansion_front_speed"
            ])
            self._sample_writer.writeheader()

        if self.events_path is not None:
            self.events_path.parent.mkdir(parents=True, exist_ok=True)
            self._event_file = self.events_path.open("w", encoding="utf-8", newline="")
            self._event_writer = csv.DictWriter(self._event_file, fieldnames=["tick", "type", "detail"])
            self._event_writer.writeheader()

    def close_live_files(self):
        for f in (self._sample_file, self._event_file):
            if f:
                f.flush()
                f.close()
        self._sample_file = None
        self._event_file = None

    def add_event(self, tick: int, event_type: str, detail: str):
        ev = {"tick": tick, "type": event_type, "detail": detail}
        if self.events and self.events[-1] == ev:
            return
        self.events.append(ev)
        self.last_event = f"{tick}: {event_type} - {detail}"
        if self._event_writer:
            self._event_writer.writerow(ev)
            self._event_file.flush()

    @staticmethod
    def _median(values):
        values = sorted(values)
        n = len(values)
        if n == 0:
            return 0.0
        mid = n // 2
        return float(values[mid] if n % 2 else (values[mid - 1] + values[mid]) / 2)

    def _background_by_parity(self, grid):
        even, odd = [], []
        h = len(grid)
        w = len(grid[0]) if h else 0
        for y in range(h):
            for x in range(w):
                if (x + y) & 1:
                    odd.append(float(grid[y][x]))
                else:
                    even.append(float(grid[y][x]))
        return self._median(even), self._median(odd)

    def _defect_mask(self, grid):
        h = len(grid)
        w = len(grid[0]) if h else 0
        even_med, odd_med = self._background_by_parity(grid)
        mask = [[False] * w for _ in range(h)]
        count = 0
        sx = sy = 0.0
        for y in range(h):
            for x in range(w):
                bg = odd_med if ((x + y) & 1) else even_med
                if abs(float(grid[y][x]) - bg) >= self.threshold:
                    mask[y][x] = True
                    count += 1
                    sx += x
                    sy += y
        center = (sx / count, sy / count) if count else (None, None)
        return mask, count, center

    def _components(self, mask):
        h = len(mask)
        w = len(mask[0]) if h else 0
        seen = [[False] * w for _ in range(h)]
        sizes = []

        for y0 in range(h):
            for x0 in range(w):
                if not mask[y0][x0] or seen[y0][x0]:
                    continue
                q = deque([(x0, y0)])
                seen[y0][x0] = True
                size = 0
                while q:
                    x, y = q.popleft()
                    size += 1
                    for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                        nx = (x + dx) % w
                        ny = (y + dy) % h
                        if mask[ny][nx] and not seen[ny][nx]:
                            seen[ny][nx] = True
                            q.append((nx, ny))
                if size >= self.min_object_cells:
                    sizes.append(size)
        sizes.sort(reverse=True)
        return sizes

    def _center_distance(self, a, b):
        if a is None or b is None:
            return 0.0
        ax, ay = a
        bx, by = b
        if ax is None or bx is None:
            return 0.0
        w, h = base.W, base.H
        dx = abs(ax - bx)
        dy = abs(ay - by)
        dx = min(dx, w - dx)
        dy = min(dy, h - dy)
        return math.sqrt(dx * dx + dy * dy)

    def _track_object_events(self, tick, objects, largest):
        if self._stable_objects is None:
            self._stable_objects = objects
            self._stable_since = tick
            self._prev_objects = objects
            if objects > 0:
                self.add_event(tick, "birth", f"first detected objects={objects}, largest={largest}")
            return

        if objects != self._prev_objects:
            self._prev_objects = objects
            self._stable_since = tick
            return

        if tick - (self._stable_since or tick) < self.event_grace:
            return

        if objects != self._stable_objects:
            old = self._stable_objects
            new = objects
            if old == 0 and new > 0:
                self.add_event(tick, "birth", f"objects {old}->{new}, largest={largest}")
            elif old > 0 and new == 0:
                self.add_event(tick, "death", f"objects {old}->0")
            elif new > old:
                self.add_event(tick, "split/birth", f"objects {old}->{new}, largest={largest}")
            elif new < old:
                self.add_event(tick, "merge/death", f"objects {old}->{new}, largest={largest}")
            self._stable_objects = objects

    def update(self, grid, tick):
        if tick % self.sample_every:
            return self.current

        mask, defect_cells, center = self._defect_mask(grid)
        sizes = self._components(mask)
        objects = len(sizes)
        largest = sizes[0] if sizes else 0

        changed = 0
        if self._prev_grid is not None:
            h = len(grid)
            w = len(grid[0]) if h else 0
            for y in range(h):
                for x in range(w):
                    if abs(float(grid[y][x]) - float(self._prev_grid[y][x])) > 0.05:
                        changed += 1
        self._prev_grid = [list(row) for row in grid]

        alive = largest >= self.min_object_cells

        if alive:
            if self.birth_tick is None:
                self.birth_tick = tick
                self.add_event(tick, "life-start", f"largest={largest}, objects={objects}")
            self.last_alive_tick = tick

            if largest > self.peak_largest:
                self.peak_largest = largest
                self.peak_tick = tick
                self.add_event(tick, "peak-largest", f"largest={largest}, objects={objects}")

            self.peak_cells = max(self.peak_cells, defect_cells)
            self.peak_objects = max(self.peak_objects, objects)

            if center[0] is not None:
                self.center_current = center
                if self.center_start is None:
                    self.center_start = center
                if self.center_prev is not None:
                    step = self._center_distance(self.center_prev, center)
                    self.total_drift += step
                    self.max_step_drift = max(self.max_step_drift, step)
                self.center_prev = center

        age = 0
        if self.birth_tick is not None and self.last_alive_tick is not None:
            age = self.last_alive_tick - self.birth_tick
            self.longest_age = max(self.longest_age, age)

        health = largest / self.peak_largest if self.peak_largest else 0.0

        if alive:
            self.identity_health_sum += health
            self.identity_health_samples += 1
            self.identity_persistence = self.identity_health_sum / max(1, self.identity_health_samples)

        field_cells = max(1, base.W * base.H)
        if self.first_large_structure_tick is None and largest >= max(self.min_object_cells, int(field_cells * 0.03)):
            self.first_large_structure_tick = tick
            self.add_event(tick, "first-large-structure", f"largest={largest}")
        if self.first_full_field_tick is None and defect_cells >= int(field_cells * 0.65):
            self.first_full_field_tick = tick
            self.add_event(tick, "field-saturation", f"defects={defect_cells}")

        if self.first_large_structure_tick is not None and self.first_full_field_tick is not None and self.first_full_field_tick > self.first_large_structure_tick:
            radius_proxy = math.sqrt(max(1, defect_cells) / math.pi)
            self.expansion_front_speed = radius_proxy / max(1, self.first_full_field_tick - self.first_large_structure_tick)

        if self.collapse_tick is not None or (self.birth_tick is not None and not alive):
            self.post_collapse_structure = defect_cells / max(1, self.peak_cells)
            # Legacy = structure left behind after living-object collapse, discounted if it is just full-field soup.
            soup_penalty = 0.35 if defect_cells > field_cells * 0.70 else 1.0
            self.legacy_score = max(0.0, min(1.0, self.post_collapse_structure * soup_penalty))
            self.information_survival = max(0.0, min(1.0,
                0.45 * self.identity_persistence +
                0.35 * self.legacy_score +
                0.20 * min(1.0, self.longest_age / max(1, tick))
            ))

        self._track_object_events(tick, objects, largest)

        if (
            not alive
            and self.birth_tick is not None
            and self.collapse_tick is None
            and self.last_alive_tick is not None
            and tick - self.last_alive_tick >= self.collapse_grace
        ):
            self.collapse_tick = self.last_alive_tick
            self.add_event(tick, "collapse", f"last_alive={self.last_alive_tick}, lifetime={self.longest_age}")
            self.add_event(tick, "legacy-check", f"post_collapse_structure={self.post_collapse_structure:.3f}, legacy={self.legacy_score:.3f}")

        self.current = {
            "objects": objects,
            "defect_cells": defect_cells,
            "largest": largest,
            "alive": alive,
            "age": age,
            "changed": changed,
            "health": health,
            "cx": center[0],
            "cy": center[1],
            "step_drift": self.max_step_drift,
            "total_drift": self.total_drift,
            "identity_persistence": self.identity_persistence,
            "legacy_score": self.legacy_score,
            "information_survival": self.information_survival,
            "post_collapse_structure": self.post_collapse_structure,
            "expansion_front_speed": self.expansion_front_speed,
        }

        sample = {
            "tick": tick,
            "alive": alive,
            "objects": objects,
            "largest": largest,
            "defect_cells": defect_cells,
            "changed": changed,
            "age": age,
            "health": round(health, 6),
            "cx": None if center[0] is None else round(center[0], 4),
            "cy": None if center[1] is None else round(center[1], 4),
            "step_drift": round(self.max_step_drift, 6),
            "total_drift": round(self.total_drift, 6),
            "identity_persistence": round(self.identity_persistence, 6),
            "legacy_score": round(self.legacy_score, 6),
            "information_survival": round(self.information_survival, 6),
            "post_collapse_structure": round(self.post_collapse_structure, 6),
            "expansion_front_speed": round(self.expansion_front_speed, 6),
        }
        self.samples.append(sample)

        if self._sample_writer:
            self._sample_writer.writerow(sample)
            self._samples_since_flush += 1
            if self._samples_since_flush >= self.live_flush_every:
                self._sample_file.flush()
                self._samples_since_flush = 0

        return self.current

    def life_stage(self):
        c = self.current
        if self.collapse_tick is not None:
            return "dead"
        if not c["alive"]:
            return "no-object"
        h = c["health"]
        if c["age"] < 200:
            return "juvenile"
        if h >= 0.75:
            return "adult"
        if h >= 0.35:
            return "old"
        return "critical"

    def status_text(self):
        c = self.current
        if self.collapse_tick is not None:
            return (
                f"DEAD at tick={self.collapse_tick} | lifetime={self.longest_age} | "
                f"peak_largest={self.peak_largest} | peak_defects={self.peak_cells} | "
                f"legacy={self.legacy_score:.2f} info={self.information_survival:.2f}"
            )
        return (
            f"{self.life_stage().upper()} | objects={c['objects']} | largest={c['largest']} | "
            f"health={c['health']:.2f} | defects={c['defect_cells']} | changed={c['changed']} | "
            f"age={c['age']} | drift={c['total_drift']:.1f} | "
            f"id={c['identity_persistence']:.2f} legacy={c['legacy_score']:.2f} info={c['information_survival']:.2f}"
        )

    def event_text(self):
        return f"event: {self.last_event}"

    def passport(self, rec, final_tick):
        m = rec.get("metrics") or {}
        return {
            "created": datetime.now().isoformat(timespec="seconds"),
            "rule_id": rec.get("rule_id"),
            "score": rec.get("score"),
            "source": rec.get("source"),
            "generation": rec.get("generation"),
            "metrics": {
                "memory_trace_score": m.get("memory_trace_score"),
                "persistent_tracks": m.get("persistent_tracks"),
                "ms_flow": m.get("ms_flow"),
                "ms_rotation_flow": m.get("ms_rotation_flow"),
                "crystal_order": m.get("crystal_order"),
                "quasi_particle_score": m.get("quasi_particle_score"),
                "information_survival": m.get("information_survival"),
                "identity_persistence": m.get("identity_persistence"),
                "legacy_score": m.get("legacy_score"),
                "post_collapse_structure": m.get("post_collapse_structure"),
                "expansion_front_speed": m.get("expansion_front_speed"),
                "collapse_stage": m.get("collapse_stage"),
            },
            "life": {
                "final_tick_observed": final_tick,
                "birth_tick": self.birth_tick,
                "last_alive_tick": self.last_alive_tick,
                "collapse_tick": self.collapse_tick,
                "longest_observed_age": self.longest_age,
                "peak_tick": self.peak_tick,
                "peak_objects": self.peak_objects,
                "peak_largest_object_cells": self.peak_largest,
                "peak_defect_cells": self.peak_cells,
                "total_center_drift": round(self.total_drift, 6),
                "max_step_drift": round(self.max_step_drift, 6),
                "final_life_stage": self.life_stage(),
                "identity_persistence_observed": round(self.identity_persistence, 6),
                "legacy_score_observed": round(self.legacy_score, 6),
                "information_survival_observed": round(self.information_survival, 6),
                "post_collapse_structure_observed": round(self.post_collapse_structure, 6),
                "expansion_front_speed_observed": round(self.expansion_front_speed, 6),
                "first_large_structure_tick": self.first_large_structure_tick,
                "field_saturation_tick": self.first_full_field_tick,
            },
            "events": self.events,
        }

    def write_outputs(self, root_dir: Path, rec, final_tick, write_log=True, write_passport=True):
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        rid = rec["rule_id"]
        out_dir = root_dir / "observation_logs/observation_XXXX + latest"
        out_dir.mkdir(parents=True, exist_ok=True)

        passport = self.passport(rec, final_tick)

        if write_passport:
            json_path = out_dir / f"rule_{rid:05d}_{stamp}_passport.json"
            json_path.write_text(json.dumps(passport, indent=2, ensure_ascii=False), encoding="utf-8")

            md_path = out_dir / f"rule_{rid:05d}_{stamp}_passport.md"
            md_path.write_text(self.passport_markdown(passport), encoding="utf-8")

            print(f"Passport saved: {json_path}")
            print(f"Passport markdown saved: {md_path}")

        if write_log:
            log_path = out_dir / f"rule_{rid:05d}_{stamp}_log.txt"
            self.write_log(log_path, rec, final_tick)
            print(f"Observation log saved: {log_path}")

    def passport_markdown(self, data):
        life = data["life"]
        metrics = data["metrics"]
        lines = [
            f"# Life Passport: Rule {data['rule_id']:05d}",
            "",
            f"- Score: **{data['score']}**",
            f"- Source: `{data['source']}`",
            f"- Generation: **{data['generation']}**",
            "",
            "## Original Metrics",
            f"- Memory: **{metrics.get('memory_trace_score')}**",
            f"- Tracks: **{metrics.get('persistent_tracks')}**",
            f"- Flow: **{metrics.get('ms_flow')}**",
            f"- Rotation: **{metrics.get('ms_rotation_flow')}**",
            f"- Crystal order: **{metrics.get('crystal_order')}**",
            f"- Quasi-particle score: **{metrics.get('quasi_particle_score')}**",
            "",
            "## Life Summary",
            f"- Birth tick: **{life.get('birth_tick')}**",
            f"- Last alive tick: **{life.get('last_alive_tick')}**",
            f"- Collapse tick: **{life.get('collapse_tick')}**",
            f"- Longest observed age: **{life.get('longest_observed_age')}**",
            f"- Peak tick: **{life.get('peak_tick')}**",
            f"- Peak objects: **{life.get('peak_objects')}**",
            f"- Peak largest object cells: **{life.get('peak_largest_object_cells')}**",
            f"- Peak defect cells: **{life.get('peak_defect_cells')}**",
            f"- Total center drift: **{life.get('total_center_drift')}**",
            f"- Final stage: **{life.get('final_life_stage')}**",
            "",
            "## Information / Legacy",
            f"- Identity persistence: **{life.get('identity_persistence_observed')}**",
            f"- Legacy score: **{life.get('legacy_score_observed')}**",
            f"- Information survival: **{life.get('information_survival_observed')}**",
            f"- Post-collapse structure: **{life.get('post_collapse_structure_observed')}**",
            f"- Expansion front speed: **{life.get('expansion_front_speed_observed')}**",
            f"- First large structure tick: **{life.get('first_large_structure_tick')}**",
            f"- Field saturation tick: **{life.get('field_saturation_tick')}**",
            "",
            "## Event Timeline",
            "",
        ]
        if data["events"]:
            for ev in data["events"]:
                lines.append(f"- tick **{ev['tick']}**: `{ev['type']}` - {ev['detail']}")
        else:
            lines.append("- No events recorded.")
        return "\n".join(lines) + "\n"

    def write_log(self, path: Path, rec, final_tick):
        data = self.passport(rec, final_tick)
        lines = [
            "Universe Search Observation Log",
            "=" * 36,
            "",
            f"Created: {data['created']}",
            f"Rule: {data['rule_id']:05d}",
            f"Score: {data['score']}",
            f"Source: {data['source']}",
            f"Generation: {data['generation']}",
            "",
            "Life observation",
            "----------------",
            json.dumps(data["life"], indent=2, ensure_ascii=False),
            "",
            "Event timeline",
            "--------------",
        ]
        for ev in data["events"]:
            lines.append(f"tick={ev['tick']} | {ev['type']} | {ev['detail']}")
        lines += ["", "Recent samples", "--------------"]
        for s in self.samples[-30:]:
            lines.append(str(s))
        path.write_text("\n".join(lines), encoding="utf-8")


# ---------------- Tk viewer ----------------

class WorldViewer:
    def __init__(self, root, rule, rec, args, observer: LifeObserver):
        self.root = root
        self.rule = rule
        self.rec = rec
        self.args = args
        self.observer = observer
        self.sim = base.FieldSim(rule)
        self.tick = 0
        self.running = True
        self.closed = False

        root.title(f"Universe Search Observer v1.3 Observation Archive - rule {rec['rule_id']:05d}")

        self.canvas = tk.Canvas(
            root,
            width=base.W * args.cell,
            height=base.H * args.cell,
            bg="black",
            highlightthickness=0,
        )
        self.canvas.pack()

        self.info = tk.Label(root, text="", anchor="w", justify="left", font=("Consolas", 9))
        self.info.pack(fill="x")

        self.rects = []
        for y in range(base.H):
            row = []
            for x in range(base.W):
                row.append(self.canvas.create_rectangle(
                    x * args.cell,
                    y * args.cell,
                    (x + 1) * args.cell,
                    (y + 1) * args.cell,
                    outline="",
                    fill="#000000",
                ))
            self.rects.append(row)

        root.bind("<space>", self.toggle)
        root.bind("<Right>", self.single_step)
        root.bind("<r>", self.reset)
        root.bind("<s>", self.save_now)
        root.bind("<Escape>", lambda e: self.close())
        root.protocol("WM_DELETE_WINDOW", self.close)

        self.draw()
        self.loop()

    def toggle(self, event=None):
        self.running = not self.running

    def single_step(self, event=None):
        self.sim.step()
        self.tick += 1
        self.draw()

    def reset(self, event=None):
        self.sim = base.FieldSim(self.rule)
        self.tick = 0
        # full observer reset would require rebuilding files; avoid silently overwriting
        self.observer.add_event(self.tick, "manual-reset", "simulation reset requested")

    def save_now(self, event=None):
        self.observer.write_outputs(Path(self.args.results_dir), self.rec, self.tick, write_log=True, write_passport=True)

    def close(self):
        if self.closed:
            return
        self.closed = True
        if self.args.log or self.args.passport:
            self.observer.write_outputs(
                Path(self.args.results_dir),
                self.rec,
                self.tick,
                write_log=self.args.log,
                write_passport=self.args.passport,
            )
        self.observer.close_live_files()
        self.root.destroy()

    def draw(self):
        for y in range(base.H):
            for x in range(base.W):
                self.canvas.itemconfig(self.rects[y][x], fill=rgb_hex(self.sim.a[y][x]))

        self.observer.update(self.sim.a, self.tick)
        m = self.rec.get("metrics") or {}
        line1 = (
            f"tick={self.tick} | rule={self.rec['rule_id']:05d} | score={self.rec.get('score')} | "
            f"memory={m.get('memory_trace_score')} tracks={m.get('persistent_tracks')} "
            f"flow={m.get('ms_flow')} rotation={m.get('ms_rotation_flow')}"
        )
        line2 = self.observer.status_text()
        line3 = self.observer.event_text()
        line4 = "space=pause/play | right=step | s=save passport | esc=close"

        self.info.config(text=f"{line1}\n{line2}\n{line3}\n{line4}")

    def loop(self):
        if self.running:
            for _ in range(self.args.speed):
                self.sim.step()
                self.tick += 1

            self.draw()

            if self.args.auto_stop and self.observer.collapse_tick is not None:
                print(self.observer.status_text())
                self.observer.write_outputs(
                    Path(self.args.results_dir),
                    self.rec,
                    self.tick,
                    write_log=self.args.log,
                    write_passport=self.args.passport,
                )
                self.running = False

            if self.args.max_ticks and self.tick >= self.args.max_ticks:
                print(f"Reached max ticks: {self.args.max_ticks}")
                self.observer.write_outputs(
                    Path(self.args.results_dir),
                    self.rec,
                    self.tick,
                    write_log=self.args.log,
                    write_passport=self.args.passport,
                )
                self.running = False

        self.root.after(self.args.delay, self.loop)


def main():
    parser = argparse.ArgumentParser(description="Universe Search Observer v1.3 Observation Archive")
    parser.add_argument("results_dir", help="Results folder, e.g. universe_search_v20_results")
    parser.add_argument("selector", help="rule id, best, top, outlier, family, list")
    parser.add_argument("extra", nargs="?", help="top number or family name")

    parser.add_argument("--cell", type=int, default=8)
    parser.add_argument("--speed", type=int, default=2)
    parser.add_argument("--delay", type=int, default=30)

    parser.add_argument("--defect-threshold", type=float, default=0.18)
    parser.add_argument("--min-object-cells", type=int, default=8)
    parser.add_argument("--collapse-grace", type=int, default=250)
    parser.add_argument("--sample-every", type=int, default=1)
    parser.add_argument("--event-grace", type=int, default=5)
    parser.add_argument("--live-flush-every", type=int, default=100)

    parser.add_argument("--auto-stop", action="store_true")
    parser.add_argument("--max-ticks", type=int, default=0)
    parser.add_argument("--log", action="store_true")
    parser.add_argument("--passport", action="store_true")
    parser.add_argument("--samples-csv", action="store_true")
    parser.add_argument("--events-csv", action="store_true")

    args = parser.parse_args()
    args.results_dir = str(args.results_dir)

    results_dir = Path(args.results_dir)
    rec = choose_record(results_dir, args.selector, args.extra)
    rule = base.rule_from_dict(rec["rule"])

    print(f"Loaded rule {rec['rule_id']:05d} from {rec['source']}")
    print(f"Score: {rec.get('score')}")
    m = rec.get("metrics") or {}
    print(
        "Metrics:",
        f"memory={m.get('memory_trace_score')}",
        f"tracks={m.get('persistent_tracks')}",
        f"flow={m.get('ms_flow')}",
        f"rotation={m.get('ms_rotation_flow')}",
        f"crystal={m.get('crystal_order')}",
        f"quasi={m.get('quasi_particle_score')}",
    )

    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_dir, observation_root, observation_id, observation_created = prepare_observation_archive(results_dir, str(rule_arg))
    samples_path = out_dir / f"rule_{rec['rule_id']:05d}_{stamp}_samples.csv" if args.samples_csv else None
    events_path = out_dir / f"rule_{rec['rule_id']:05d}_{stamp}_events.csv" if args.events_csv else None

    observer = LifeObserver(
        threshold=args.defect_threshold,
        min_object_cells=args.min_object_cells,
        collapse_grace=args.collapse_grace,
        sample_every=args.sample_every,
        event_grace=args.event_grace,
        live_flush_every=args.live_flush_every,
        samples_path=samples_path,
        events_path=events_path,
    )

    if tk is None:
        raise SystemExit("tkinter is not available.")

    root = tk.Tk()
    WorldViewer(root, rule, rec, args, observer)
    root.mainloop()

try:
    life = observer.make_passport().get("life", {}) if hasattr(observer, "make_passport") else {}
    meta = {
        "observation": observation_id,
        "created": observation_created,
        "rule_label": str(rule_arg),
        "rule_id": getattr(rule, "rule_id", None),
        "ticks": getattr(observer, "tick", None),
        "final_stage": life.get("final_life_stage"),
        "longest_age": life.get("longest_age"),
        "peak_largest": life.get("peak_largest"),
        "peak_defects": life.get("peak_defects"),
        "identity_persistence": life.get("identity_persistence_observed"),
        "legacy_score": life.get("legacy_score_observed"),
        "information_survival": life.get("information_survival_observed"),
        "post_collapse_structure": life.get("post_collapse_structure_observed"),
        "folder": str(log_dir).replace("\\", "/"),
    }
    finalize_observation_archive(log_dir, observation_root, meta)
    print(f"Observation archived: {log_dir}")
except Exception as e:
    print(f"Observation archive warning: {e!r}")



if __name__ == "__main__":
    main()
