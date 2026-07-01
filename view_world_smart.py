#!/usr/bin/env python3
"""
Universe Search Smart Viewer v1.1

Put this file next to:
    universe_search.py
    universe_search_core.py

Examples:
    python view_world_smart.py universe_search_v20_results best
    python view_world_smart.py universe_search_v20_results 487
    python view_world_smart.py universe_search_v20_results outlier
    python view_world_smart.py universe_search_v20_results top 3
    python view_world_smart.py universe_search_v20_results family "Persistent Entity Garden"
    python view_world_smart.py universe_search_v20_results list
    python view_world_smart.py universe_search_v20_results best --save-gif
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

try:
    import tkinter as tk
except Exception:
    tk = None

try:
    import universe_search_core as base
except Exception as e:
    print("Could not import universe_search_core.py")
    print("Put this file in the same folder as universe_search_core.py")
    print("Import error:", repr(e))
    raise


def iter_dicts(obj):
    if isinstance(obj, dict):
        yield obj
        for value in obj.values():
            yield from iter_dicts(value)
    elif isinstance(obj, list):
        for value in obj:
            yield from iter_dicts(value)


def rule_id_from_any(value):
    if isinstance(value, int):
        return value
    text = str(value).strip().lower()
    m = re.search(r"(\d+)", text)
    return int(m.group(1)) if m else None


def collect_world_records(results_dir: Path):
    records = []

    files = sorted(results_dir.glob("generation*.json"))
    files += sorted(results_dir.glob("best*.json"))

    atlas_dir = results_dir / "atlas"
    if atlas_dir.exists():
        files += sorted(atlas_dir.rglob("metrics.json"))
        files += sorted(atlas_dir.rglob("rule.json"))

    for path in files:
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            continue

        for node in iter_dicts(data):
            if not isinstance(node, dict):
                continue

            rule = None
            metrics = None
            score = None

            if isinstance(node.get("rule"), dict):
                rule = node.get("rule")
                metrics = node.get("metrics") if isinstance(node.get("metrics"), dict) else {}
                score = node.get("score")

            elif "rule_id" in node and any(k in node for k in ("weights", "thresholds", "seed", "parent_a", "parent_b")):
                rule = node
                metrics = {}
                score = None

            if not isinstance(rule, dict):
                continue

            rid = rule.get("rule_id")
            if rid is None:
                continue

            gen = None
            m = re.search(r"generation_(\d+)", path.name)
            if m:
                gen = int(m.group(1))

            records.append({
                "rule_id": int(rid),
                "score": score if isinstance(score, (int, float)) else None,
                "metrics": metrics or {},
                "rule": rule,
                "source": str(path),
                "generation": gen,
                "class": (metrics or {}).get("class") or (metrics or {}).get("world_class") or (metrics or {}).get("classification"),
            })

    # deduplicate by rule_id, keep highest score if present
    by_id = {}
    for rec in records:
        rid = rec["rule_id"]
        old = by_id.get(rid)
        if old is None:
            by_id[rid] = rec
        else:
            old_score = old["score"] if old["score"] is not None else -1e18
            new_score = rec["score"] if rec["score"] is not None else -1e18
            if new_score >= old_score:
                by_id[rid] = rec

    return list(by_id.values())


def load_analyzer_report(results_dir: Path):
    path = results_dir / "research_report" / "research_summary.json"
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def choose_record(results_dir: Path, selector: str, extra: str | None = None):
    records = collect_world_records(results_dir)
    if not records:
        raise SystemExit(f"No world records found in {results_dir}")

    selector = str(selector).strip()

    rid = rule_id_from_any(selector)
    if rid is not None and selector.lower() not in ("best", "outlier", "list", "top", "family"):
        for rec in records:
            if rec["rule_id"] == rid:
                return rec
        raise SystemExit(f"Rule {rid} not found.")

    scored = [r for r in records if r["score"] is not None]
    scored.sort(key=lambda r: r["score"], reverse=True)

    if selector == "best":
        return scored[0] if scored else records[0]

    if selector == "top":
        n = int(extra or "1")
        if n < 1:
            n = 1
        if not scored:
            return records[0]
        return scored[min(n - 1, len(scored) - 1)]

    if selector == "outlier":
        md = results_dir / "research_report" / "research_summary.md"
        if md.exists():
            text = md.read_text(encoding="utf-8", errors="ignore")
            m = re.search(r"### rule\s+(\d+)", text, flags=re.IGNORECASE)
            if m:
                rid = int(m.group(1))
                for rec in records:
                    if rec["rule_id"] == rid:
                        return rec
        # fallback: highest flow+motion weirdness
        def weird(r):
            m = r["metrics"]
            return (
                float(m.get("ms_flow", 0) or 0) * 4 +
                float(m.get("ms_rotation_flow", 0) or 0) * 4 +
                float(m.get("defect_motion", 0) or 0) * 2 +
                float(m.get("quasi_particle_score", 0) or 0)
            )
        return max(records, key=weird)

    if selector == "family":
        fam = (extra or "").lower()
        if not fam:
            raise SystemExit('Family name required, e.g. family "Entity Memory Ecology"')
        matches = []
        for r in records:
            m = r["metrics"]
            klass = (
                r.get("class") or
                m.get("class") or
                m.get("world_class") or
                m.get("classification") or
                ""
            )
            if fam in str(klass).lower():
                matches.append(r)
        if not matches:
            raise SystemExit(f"No records found for family: {extra}")
        matches.sort(key=lambda r: r["score"] if r["score"] is not None else -1e18, reverse=True)
        return matches[0]

    if selector == "list":
        print("Top available worlds:")
        for i, r in enumerate(scored[:20], 1):
            m = r["metrics"]
            print(
                f"{i:02d}. rule {r['rule_id']:05d} "
                f"score={r['score'] if r['score'] is not None else 'n/a'} "
                f"gen={r.get('generation')} "
                f"memory={m.get('memory_trace_score')} "
                f"tracks={m.get('persistent_tracks')} "
                f"flow={m.get('ms_flow')} "
                f"crystal={m.get('crystal_order')} "
                f"quasi={m.get('quasi_particle_score')}"
            )
        raise SystemExit(0)

    raise SystemExit(f"Unknown selector: {selector}")


def rgb_hex(a: float):
    a = max(0.0, min(1.0, float(a)))
    blue = int((1.0 - a) * 230)
    yellow = int(a * 255)
    green = int(120 + 90 * (1.0 - abs(a - 0.5) * 2))
    return f"#{yellow:02x}{green:02x}{blue:02x}"


class WorldViewer:
    def __init__(self, root, rule, title, cell=8, step_per_frame=2, delay_ms=30):
        self.root = root
        self.rule = rule
        self.sim = base.FieldSim(rule)
        self.cell = cell
        self.step_per_frame = step_per_frame
        self.delay_ms = delay_ms
        self.tick = 0
        self.running = True

        root.title(title)
        self.canvas = tk.Canvas(root, width=base.W * cell, height=base.H * cell, bg="black", highlightthickness=0)
        self.canvas.pack()

        self.info = tk.Label(root, text="", anchor="w")
        self.info.pack(fill="x")

        self.rects = []
        for y in range(base.H):
            row = []
            for x in range(base.W):
                row.append(self.canvas.create_rectangle(
                    x * cell, y * cell, (x + 1) * cell, (y + 1) * cell,
                    outline="", fill="#000000"
                ))
            self.rects.append(row)

        root.bind("<space>", self.toggle)
        root.bind("<Right>", self.single_step)
        root.bind("<r>", self.reset)
        root.bind("<Escape>", lambda e: root.destroy())

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
        self.draw()

    def draw(self):
        for y in range(base.H):
            for x in range(base.W):
                self.canvas.itemconfig(self.rects[y][x], fill=rgb_hex(self.sim.a[y][x]))
        self.info.config(text=f"tick={self.tick}    space=pause/play    right=step    r=reset    esc=close")

    def loop(self):
        if self.running:
            for _ in range(self.step_per_frame):
                self.sim.step()
                self.tick += 1
            self.draw()
        self.root.after(self.delay_ms, self.loop)


def save_gif(rule, out_path: Path, burn=300, frames=80, stride=6, cell=4):
    try:
        from PIL import Image
    except Exception:
        print("Pillow is not installed. Run: pip install pillow")
        return False

    sim = base.FieldSim(rule)
    for _ in range(burn):
        sim.step()

    images = []
    for _ in range(frames):
        img = Image.new("RGB", (base.W, base.H))
        pix = img.load()
        for y in range(base.H):
            for x in range(base.W):
                a = max(0.0, min(1.0, float(sim.a[y][x])))
                blue = int((1.0 - a) * 230)
                yellow = int(a * 255)
                green = int(120 + 90 * (1.0 - abs(a - 0.5) * 2))
                pix[x, y] = (yellow, green, blue)
        img = img.resize((base.W * cell, base.H * cell), Image.Resampling.NEAREST)
        images.append(img)
        for _ in range(stride):
            sim.step()

    out_path.parent.mkdir(parents=True, exist_ok=True)
    images[0].save(out_path, save_all=True, append_images=images[1:], duration=80, loop=0)
    print(f"Saved GIF: {out_path}")
    return True


def main():
    parser = argparse.ArgumentParser(description="Smart viewer for Universe Search worlds.")
    parser.add_argument("results_dir", help="Results folder, e.g. universe_search_v20_results")
    parser.add_argument("selector", help="rule id, best, top, outlier, family, list")
    parser.add_argument("extra", nargs="?", help="top number or family name")
    parser.add_argument("--cell", type=int, default=8)
    parser.add_argument("--speed", type=int, default=2)
    parser.add_argument("--delay", type=int, default=30)
    parser.add_argument("--save-gif", action="store_true")
    parser.add_argument("--gif-frames", type=int, default=80)
    parser.add_argument("--gif-burn", type=int, default=300)
    parser.add_argument("--gif-stride", type=int, default=6)
    args = parser.parse_args()

    results_dir = Path(args.results_dir)
    rec = choose_record(results_dir, args.selector.lower(), args.extra)
    rule = base.rule_from_dict(rec["rule"])

    print(f"Loaded rule {rec['rule_id']:05d} from {rec['source']}")
    if rec["score"] is not None:
        print(f"Score: {rec['score']}")
    m = rec["metrics"]
    print(
        "Metrics:",
        f"memory={m.get('memory_trace_score')}",
        f"tracks={m.get('persistent_tracks')}",
        f"flow={m.get('ms_flow')}",
        f"rotation={m.get('ms_rotation_flow')}",
        f"crystal={m.get('crystal_order')}",
        f"defects={m.get('defect_density')}",
        f"quasi={m.get('quasi_particle_score')}",
    )

    if args.save_gif:
        out = results_dir / "viewer_exports" / f"rule_{rec['rule_id']:05d}.gif"
        save_gif(rule, out, burn=args.gif_burn, frames=args.gif_frames, stride=args.gif_stride, cell=max(1, args.cell // 2))
        return

    if tk is None:
        print("tkinter is not available. Use --save-gif instead.")
        raise SystemExit(1)

    root = tk.Tk()
    WorldViewer(root, rule, f"Universe Search Viewer - rule {rec['rule_id']:05d}", cell=args.cell, step_per_frame=args.speed, delay_ms=args.delay)
    root.mainloop()


if __name__ == "__main__":
    main()
