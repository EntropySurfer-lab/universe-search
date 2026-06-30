#!/usr/bin/env python3
# Universe Search v2.1.4 - Production Ready Parallel Crystal Wrapper
# Put this file in the same folder as universe_search_v10_4_observer_niches.py

import json
import math
import os
import random
import sys
import time
import hashlib
import collections
import atexit
from pathlib import Path
from concurrent.futures import ProcessPoolExecutor, as_completed

try:
    import universe_search_v10_4_observer_niches as base
except Exception as e:
    print('Could not import universe_search_v10_4_observer_niches.py')
    print('Put this file in the same folder as your v10.4 script.')
    print('Import error:', repr(e))
    raise

# ---------------- Settings ----------------

OUT_DIR = Path('universe_search_v20_results')
ATLAS_DIR = OUT_DIR / 'atlas'
CHECKPOINT_FILE = OUT_DIR / 'checkpoint_observer_niches.json'
ATLAS_INDEX_FILE = ATLAS_DIR / 'atlas_index.json'
ATLAS_INDEX_JSONL = ATLAS_DIR / 'atlas_index.jsonl'
CRYSTAL_CACHE_FILE = OUT_DIR / 'crystal_defect_cache.json'
DIVERSITY_SKELETON_FILE = OUT_DIR / 'diversity_skeleton.json'

PARALLEL = True
WORKERS = max(1, min(6, (os.cpu_count() or 2) // 2 or 1))

# Prevent worker processes from writing shared cache files.
MAIN_PID = int(os.environ.get('UNIVERSE_SEARCH_MAIN_PID', os.getpid()))

ATLAS_TOP_GLOBAL = 6
ATLAS_TOP_NICHES = 8
ATLAS_PREVIEW_TICKS = 900
ATLAS_PREVIEW_CELL = 5
ATLAS_MIN_SCORE = 60.0
ATLAS_SAVE_GIF = True

# Keep this modest. GIF generation runs in the main process.
ATLAS_GIF_TOP_LIMIT = 3
ATLAS_GIF_TICKS = 600
ATLAS_GIF_FRAMES = 24
ATLAS_GIF_STRIDE = 8
ATLAS_GIF_CELL = 4

CRYSTAL_DEFECT_ANALYSIS = True
CRYSTAL_DEFECT_BONUS = 28.0
CRYSTAL_BURN_TICKS = 360
CRYSTAL_FRAMES = 28
CRYSTAL_FRAME_STRIDE = 6
CRYSTAL_MAX_PERIOD = 8
CRYSTAL_DEFECT_TOL = 0.22
_crystal_cache = None
NOVELTY_ARCHIVE_MAXLEN = 2000
CRYSTAL_CACHE_MAX_ITEMS = 5000

POPULATION = base.POPULATION
GENERATIONS = base.GENERATIONS
KEEP_TOP = base.KEEP_TOP
ELITES = base.ELITES
RANDOM_IMMIGRANTS = base.RANDOM_IMMIGRANTS
OBSERVER_COUNT = base.OBSERVER_COUNT
OBSERVER_ELITES = base.OBSERVER_ELITES

# ---------------- Helpers ----------------

def now_s():
    return time.strftime('%H:%M:%S')


def configure_base_paths():
    base.OUT_DIR = OUT_DIR
    base.HUMAN_FAV_FILE = OUT_DIR / 'human_favorites.json'
    base.OBSERVER_ARCHIVE_FILE = OUT_DIR / 'observer_profiles.json'


def atomic_write_text(path, text, encoding='utf-8'):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + '.tmp')
    tmp.write_text(text, encoding=encoding)
    tmp.replace(path)


def atomic_write_json(path, payload, indent=2):
    atomic_write_text(path, json.dumps(payload, indent=indent, ensure_ascii=False), encoding='utf-8')


def rule_hash(rule):
    raw = base.rule_signature(rule).encode('utf-8')
    return hashlib.sha1(raw).hexdigest()[:12]


def slug(s):
    s = ''.join(ch.lower() if ch.isalnum() else '_' for ch in str(s))
    while '__' in s:
        s = s.replace('__', '_')
    return s.strip('_')[:50] or 'unknown'


def stars(x, max_value=1.0):
    v = max(0.0, min(1.0, float(x) / max_value))
    n = int(round(v * 5))
    return '★' * n + '☆' * (5 - n)


def load_crystal_cache():
    global _crystal_cache
    if _crystal_cache is not None:
        return _crystal_cache
    if CRYSTAL_CACHE_FILE.exists():
        try:
            _crystal_cache = json.loads(CRYSTAL_CACHE_FILE.read_text(encoding='utf-8'))
        except Exception:
            _crystal_cache = {}
    else:
        _crystal_cache = {}
    return _crystal_cache


def save_crystal_cache():
    if os.getpid() != MAIN_PID or _crystal_cache is None:
        return
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    items = list(_crystal_cache.items())[-CRYSTAL_CACHE_MAX_ITEMS:]
    atomic_write_json(CRYSTAL_CACHE_FILE, dict(items), indent=2)


atexit.register(save_crystal_cache)


def empty_crystal_metrics(error=None):
    return {
        'crystal_order': 0.0,
        'crystal_period_x': 0,
        'crystal_period_y': 0,
        'crystal_error': 1.0,
        'defect_density': 0.0,
        'defect_density_var': 0.0,
        'defect_persistence': 0.0,
        'defect_motion': 0.0,
        'defect_density_window': 0.0,
        'quasi_particle_score': 0.0,
        'crystal_cache_hit': False,
        'crystal_analysis_error': error,
    }


def safe_crystal_metrics(metrics):
    out = empty_crystal_metrics(metrics.get('crystal_analysis_error') if isinstance(metrics, dict) else 'invalid crystal metrics')
    if isinstance(metrics, dict):
        out.update(metrics)
    return out


def merge_crystal_into_main_cache(rule, metrics):
    if os.getpid() != MAIN_PID or not isinstance(metrics, dict):
        return
    if metrics.get('crystal_cache_hit'):
        return
    cache = load_crystal_cache()
    key = rule_hash(rule)
    cached_payload = {k: v for k, v in metrics.items() if k.startswith('crystal_') or k.startswith('defect_') or k == 'quasi_particle_score'}
    cache[key] = cached_payload


def classify_world(m):
    active = m.get('active', 0.0)
    edge = m.get('edge', 0.0)
    life = m.get('ms_local_life', 0.0)
    flow = m.get('ms_flow', 0.0)
    rot = m.get('ms_rotation_flow', 0.0)
    mem = max(0.0, m.get('memory_trace_score', 0.0)) / 120.0
    tracks = m.get('persistent_tracks', 0)
    ent_q = m.get('best_entity_quality', 0.0)
    reg = m.get('best_region_score', 0.0)
    cr = m.get('cosmic_recovery', 0.0)
    nested = m.get('nested_score_raw', 0.0)

    if active > 0.96 and edge < 0.04: return 'Degenerate Smooth Soup'
    if active < 0.02: return 'Dead Empty Field'
    if tracks >= 30 and ent_q >= 0.65 and life >= 0.55:
        if mem >= 0.55: return 'Entity Memory Ecology'
        return 'Persistent Entity Garden'
    if flow > 0.08 and rot > 0.06 and life >= 0.55: return 'Rotating Flow World'
    if flow > 0.08 and life >= 0.50: return 'Flow World'
    if mem >= 0.60 and cr >= 0.45: return 'Recovery Memory World'
    if reg >= 0.45 and nested >= 0.55: return 'Living Boundary Region'
    if nested >= 0.60 and life >= 0.50: return 'Nested Local Life'

    qps = m.get('quasi_particle_score', 0.0)
    xtal = m.get('crystal_order', 0.0)
    dd = m.get('defect_density', 0.0)
    if qps >= 0.42 and xtal >= 0.55: return 'Crystal Defect Ecology'
    if xtal >= 0.72 and 0.005 <= dd <= 0.22: return 'Almost Crystal With Defects'
    if xtal >= 0.78 and dd < 0.005: return 'Clean Crystal'
    if cr >= 0.65: return 'Resilient Scaffold'
    return 'Weird Unknown'


def _field_to_matrix(sim):
    return [[float(sim.a[y][x]) for x in range(base.W)] for y in range(base.H)]


def _best_crystal_unit(frame, max_period=CRYSTAL_MAX_PERIOD):
    H, W = base.H, base.W
    best = None
    for py in range(1, max_period + 1):
        for px in range(1, max_period + 1):
            sums = [[0.0 for _ in range(px)] for __ in range(py)]
            counts = [[0 for _ in range(px)] for __ in range(py)]
            for y in range(H):
                yy = y % py
                row = frame[y]
                for x in range(W):
                    xx = x % px
                    sums[yy][xx] += row[x]
                    counts[yy][xx] += 1
            tile = [[sums[y][x] / max(1, counts[y][x]) for x in range(px)] for y in range(py)]
            err = 0.0
            for y in range(H):
                ty = y % py
                row = frame[y]
                for x in range(W):
                    err += abs(row[x] - tile[ty][x % px])
            err /= max(1, W * H)
            parsimony = 1.0 - 0.018 * (px * py - 1)
            order = max(0.0, (1.0 - err / 0.50) * parsimony)
            if best is None or order > best[0]:
                recon = [[tile[y % py][x % px] for x in range(W)] for y in range(H)]
                best = (order, px, py, err, recon)
    return best


def _mask_stats(mask):
    H, W = base.H, base.W
    n = 0
    sx = 0.0
    sy = 0.0
    for y in range(H):
        row = mask[y]
        for x, v in enumerate(row):
            if v:
                n += 1
                sx += x
                sy += y
    if n <= 0: return 0, None
    return n, (sx / n, sy / n)


def _jaccard(a, b):
    inter = 0
    union = 0
    for y in range(base.H):
        ar = a[y]; br = b[y]
        for x in range(base.W):
            av = ar[x]; bv = br[x]
            if av or bv:
                union += 1
                if av and bv: inter += 1
    return inter / union if union else 0.0


def analyze_crystal_defects(rule):
    if not CRYSTAL_DEFECT_ANALYSIS:
        return {}
    try:
        sim = base.FieldSim(rule)
        for _ in range(CRYSTAL_BURN_TICKS):
            sim.step()

        frames = []
        for _ in range(CRYSTAL_FRAMES):
            frames.append(_field_to_matrix(sim))
            for __ in range(CRYSTAL_FRAME_STRIDE):
                sim.step()

        order, px, py, err, recon = _best_crystal_unit(frames[-1])
        masks = []
        densities = []
        centroids = []
        for frame in frames:
            mask = []
            n = 0
            for y in range(base.H):
                row = []
                for x in range(base.W):
                    is_defect = abs(frame[y][x] - recon[y][x]) > CRYSTAL_DEFECT_TOL
                    row.append(is_defect)
                    if is_defect: n += 1
                mask.append(row)
            masks.append(mask)
            densities.append(n / max(1, base.W * base.H))
            _, c = _mask_stats(mask)
            centroids.append(c)

        density = sum(densities) / len(densities)
        density_var = sum((d - density) ** 2 for d in densities) / len(densities)
        if len(masks) > 1:
            persistence = sum(_jaccard(masks[i], masks[i + 1]) for i in range(len(masks) - 1)) / (len(masks) - 1)
        else:
            persistence = 0.0

        moves = []
        for a, b in zip(centroids, centroids[1:]):
            if a is not None and b is not None:
                dx = abs(a[0] - b[0]); dy = abs(a[1] - b[1])
                dx = min(dx, base.W - dx); dy = min(dy, base.H - dy)
                moves.append(math.sqrt(dx * dx + dy * dy) / max(base.W, base.H))
        motion = min(1.0, (sum(moves) / len(moves)) * 8.0) if moves else 0.0

        if density <= 0.0: density_window = 0.0
        elif density < 0.015: density_window = density / 0.015
        elif density <= 0.18: density_window = 1.0
        elif density < 0.34: density_window = 1.0 - (density - 0.18) / 0.16
        else: density_window = 0.0
        density_window = max(0.0, min(1.0, density_window))

        persistence_window = max(0.0, 1.0 - abs(persistence - 0.45) / 0.45)
        dynamics = max(persistence_window, min(1.0, 0.55 * persistence + 0.45 * motion))
        quasi = max(0.0, min(1.0, order * density_window * dynamics))

        return {
            'crystal_order': round(order, 6),
            'crystal_period_x': px,
            'crystal_period_y': py,
            'crystal_error': round(err, 6),
            'defect_density': round(density, 6),
            'defect_density_var': round(density_var, 8),
            'defect_persistence': round(persistence, 6),
            'defect_motion': round(motion, 6),
            'defect_density_window': round(density_window, 6),
            'quasi_particle_score': round(quasi, 6),
        }
    except Exception as e:
        return {'crystal_analysis_error': repr(e)}


def atlas_report_text(rule, score, metrics, gen, score_mode, source):
    klass = classify_world(metrics)
    lines = [
        f'World: Rule {rule.rule_id:05d}',
        f'Class: {klass}',
        f'Discovered/updated in generation: {gen}',
        f'Source: {source}',
        f'Score: {score:.3f}',
        '',
        'Core signals:',
        f'  Life:        {stars(metrics.get("ms_local_life",0))}  {metrics.get("ms_local_life",0):.3f}',
        f'  Memory:      {stars(max(0,metrics.get("memory_trace_score",0))/120)}  {metrics.get("memory_trace_score",0):.1f}',
        f'  Flow:        {stars(metrics.get("ms_flow",0), 0.35)}  {metrics.get("ms_flow",0):.4f}',
        f'  Rotation:    {stars(metrics.get("ms_rotation_flow",0), 0.25)}  {metrics.get("ms_rotation_flow",0):.4f}',
        f'  Recovery:    {stars(metrics.get("cosmic_recovery",0))}  {metrics.get("cosmic_recovery",0):.3f}',
        f'  Region:      {stars(metrics.get("best_region_score",0))}  {metrics.get("best_region_score",0):.3f}',
        f'  Entity Q:    {stars(metrics.get("best_entity_quality",0))}  {metrics.get("best_entity_quality",0):.3f}',
        f'  Crystal:     {stars(metrics.get("crystal_order",0))}  {metrics.get("crystal_order",0):.3f}',
        f'  Defects:     {stars(metrics.get("defect_density_window",0))}  density={metrics.get("defect_density",0):.4f} persist={metrics.get("defect_persistence",0):.3f} move={metrics.get("defect_motion",0):.3f}',
        f'  Quasi-score: {stars(metrics.get("quasi_particle_score",0))}  {metrics.get("quasi_particle_score",0):.3f}',
        '',
        'Raw metrics:'
    ]
    for k in ['active','edge','boundary_activity','islands','nested_score_raw','ms_local_life','persistent_tracks','entity_count','best_entity_quality','best_region_score','macro_scaffold','memory_trace_score','cosmic_recovery','crystal_order','crystal_period_x','crystal_period_y','crystal_error','defect_density','defect_persistence','defect_motion','quasi_particle_score','observer_id','observer_score','observer_archetype','post_test_truth']:
        if k in metrics:
            lines.append(f'  {k}: {metrics[k]}')
    lines.extend([
        '',
        'Observer note:',
        f'  {metrics.get("observer_note", "no note")}',
        '',
        'Rule lineage:',
        f'  parent_a: {rule.parent_a}',
        f'  parent_b: {rule.parent_b}',
        f'  seed: {rule.seed}',
        '',
        'Interpretation:',
        '  This is an automatically generated field note. Open the rule in the viewer',
        '  before treating this classification as real. The Atlas is a map, not a verdict.'
    ])
    return '\n'.join(lines) + '\n'


def cell_rgb_from_value(a):
    blue = int((1.0 - a) * 230)
    yellow = int(a * 255)
    green = int(120 + 90 * (1.0 - abs(a - 0.5) * 2))
    return yellow, green, blue


def save_preview_png(rule, path, ticks=ATLAS_PREVIEW_TICKS, cell=ATLAS_PREVIEW_CELL):
    try:
        from PIL import Image
    except Exception:
        return False
    sim = base.FieldSim(rule)
    for _ in range(ticks):
        sim.step()
    img = Image.new('RGB', (base.W, base.H))
    pix = img.load()
    for y in range(base.H):
        for x in range(base.W):
            pix[x, y] = cell_rgb_from_value(sim.a[y][x])
    img = img.resize((base.W * cell, base.H * cell), Image.Resampling.NEAREST)
    img.save(path)
    return True


def save_preview_gif(rule, path, ticks=ATLAS_GIF_TICKS, frames=ATLAS_GIF_FRAMES, stride=ATLAS_GIF_STRIDE, cell=ATLAS_GIF_CELL):
    try:
        from PIL import Image
    except Exception:
        return False
    sim = base.FieldSim(rule)
    for _ in range(ticks):
        sim.step()
    images = []
    for _ in range(frames):
        img = Image.new('RGB', (base.W, base.H))
        pix = img.load()
        for y in range(base.H):
            for x in range(base.W):
                pix[x, y] = cell_rgb_from_value(sim.a[y][x])
        img = img.resize((base.W * cell, base.H * cell), Image.Resampling.NEAREST)
        images.append(img)
        for __ in range(stride):
            sim.step()
    if not images: return False
    images[0].save(path, save_all=True, append_images=images[1:], duration=80, loop=0)
    return True


def load_atlas_index():
    if ATLAS_INDEX_FILE.exists():
        try: return json.loads(ATLAS_INDEX_FILE.read_text(encoding='utf-8'))
        except Exception: return []
    return []


def save_atlas_index(index):
    ATLAS_DIR.mkdir(parents=True, exist_ok=True)
    index_sorted = sorted(index, key=lambda x: x.get('score', 0.0), reverse=True)
    atomic_write_json(ATLAS_INDEX_FILE, index_sorted, indent=2)
    jsonl_text = ''.join(json.dumps(item, ensure_ascii=False) + '\n' for item in index_sorted)
    atomic_write_text(ATLAS_INDEX_JSONL, jsonl_text, encoding='utf-8')


def add_to_atlas(gen, score_mode, items):
    ATLAS_DIR.mkdir(parents=True, exist_ok=True)
    index = load_atlas_index()
    by_key = {item.get('key'): item for item in index if item.get('key')}
    added = []
    for atlas_rank, (source, score, rule, metrics) in enumerate(items, 1):
        if metrics.get('eval_error') is not None:
            continue
        if score < ATLAS_MIN_SCORE and metrics.get('post_test_truth', 0) in (None, 0):
            continue
        h = rule_hash(rule)
        klass = classify_world(metrics)
        key = h
        folder = ATLAS_DIR / f'{slug(klass)}' / f'rule_{rule.rule_id:05d}_{h}'
        folder.mkdir(parents=True, exist_ok=True)
        atomic_write_json(folder / 'rule.json', base.rule_to_dict(rule), indent=2)
        atomic_write_json(folder / 'metrics.json', metrics, indent=2)
        atomic_write_text(folder / 'report.txt', atlas_report_text(rule, score, metrics, gen, score_mode, source), encoding='utf-8')

        preview_path = folder / 'preview.png'
        if not preview_path.exists():
            save_preview_png(rule, preview_path)

        gif_path = folder / 'preview.gif'
        make_gif = ATLAS_SAVE_GIF and atlas_rank <= ATLAS_GIF_TOP_LIMIT
        if make_gif and not gif_path.exists():
            save_preview_gif(rule, gif_path)

        entry = {
            'key': key, 'rule_id': rule.rule_id, 'class': klass, 'generation': gen,
            'score_mode': score_mode, 'score': score, 'source': source,
            'folder': str(folder).replace('\\', '/'),
            'preview': str(preview_path).replace('\\', '/') if preview_path.exists() else None,
            'preview_gif': str(gif_path).replace('\\', '/') if gif_path.exists() else None,
            'active': metrics.get('active'), 'edge': metrics.get('edge'), 'life': metrics.get('ms_local_life'),
            'flow': metrics.get('ms_flow'), 'rotation': metrics.get('ms_rotation_flow'), 'memory': metrics.get('memory_trace_score'),
            'recovery': metrics.get('cosmic_recovery'), 'region': metrics.get('best_region_score'), 'entities': metrics.get('entity_count'),
            'tracks': metrics.get('persistent_tracks'), 'observer_id': metrics.get('observer_id'), 'observer_archetype': metrics.get('observer_archetype'),
            'observer_note': metrics.get('observer_note'), 'post_test_truth': metrics.get('post_test_truth'), 'crystal_order': metrics.get('crystal_order'),
            'defect_density': metrics.get('defect_density'), 'defect_persistence': metrics.get('defect_persistence'), 'defect_motion': metrics.get('defect_motion'),
            'quasi_particle_score': metrics.get('quasi_particle_score'),
        }
        if key not in by_key or score > by_key[key].get('score', -1e9):
            by_key[key] = entry
        added.append(entry)
    save_atlas_index(list(by_key.values()))
    if added:
        print(f'  atlas: {len(added)} entries touched; index={ATLAS_INDEX_FILE}')


def select_atlas_items(results, score_mode):
    chosen = []
    seen = set()
    results = [r for r in results if r[2].get('eval_error') is None]
    for score, rule, metrics in results[:ATLAS_TOP_GLOBAL]:
        sig = base.rule_signature(rule)
        if sig not in seen:
            chosen.append(('global_top', score, rule, metrics)); seen.add(sig)
    if score_mode == 'observer_niches':
        for niche, (score, rule, metrics) in base.niche_champions(results)[:ATLAS_TOP_NICHES]:
            sig = base.rule_signature(rule)
            if sig not in seen:
                chosen.append((f'niche:{niche}', score, rule, metrics)); seen.add(sig)
    records = [
        ('record_tracks', lambda m: m.get('persistent_tracks', 0)),
        ('record_flow', lambda m: m.get('ms_flow', 0.0)),
        ('record_memory', lambda m: m.get('memory_trace_score', 0.0)),
        ('record_recovery', lambda m: m.get('cosmic_recovery', 0.0)),
        ('record_region', lambda m: m.get('best_region_score', 0.0)),
        ('record_quasiparticle', lambda m: m.get('quasi_particle_score', 0.0)),
        ('record_crystal_defects', lambda m: m.get('crystal_order', 0.0) * m.get('defect_density_window', 0.0)),
    ]
    for name, fn in records:
        if not results: continue
        score, rule, metrics = max(results, key=lambda x: fn(x[2]))
        sig = base.rule_signature(rule)
        if sig not in seen and fn(metrics) > 0:
            chosen.append((name, score, rule, metrics)); seen.add(sig)
    return chosen

# ---------------- Parallel Evaluation ----------------

def evaluate_one_worker(args):
    configure_base_paths()
    idx, rule_dict, internal_mode, cached_crystal = args
    rule = base.rule_from_dict(rule_dict)
    try:
        score, metrics, _ = base.score_rule(rule, internal_mode)
        metrics['eval_error'] = None
    except Exception as e:
        metrics = {
            'active': 0.0, 'edge': 0.0, 'boundary_activity': 0.0, 'islands': 0,
            'ms_local_life': 0.0, 'ms_flow': 0.0, 'ms_rotation_flow': 0.0,
            'memory_trace_score': 0.0, 'cosmic_recovery': 0.0,
            'degeneracy_penalty': 999.0, 'degeneracy_penalty_raw': 999.0,
            'eval_error': repr(e),
        }
        metrics.update(empty_crystal_metrics('skipped because score_rule failed'))
        return idx, -1e9, base.rule_to_dict(rule), metrics

    if CRYSTAL_DEFECT_ANALYSIS:
        if isinstance(cached_crystal, dict):
            crystal = safe_crystal_metrics(cached_crystal)
            crystal['crystal_cache_hit'] = True
        else:
            try:
                crystal = safe_crystal_metrics(analyze_crystal_defects(rule))
                crystal['crystal_cache_hit'] = False
            except Exception as e:
                crystal = empty_crystal_metrics(repr(e))
        metrics.update(crystal)
    else:
        metrics.update(empty_crystal_metrics('disabled'))

    return idx, score, base.rule_to_dict(rule), metrics


def evaluate_population(population, internal_mode, workers=WORKERS):
    cache = load_crystal_cache() if CRYSTAL_DEFECT_ANALYSIS else {}
    jobs = []
    for i, r in enumerate(population):
        cached = cache.get(rule_hash(r)) if CRYSTAL_DEFECT_ANALYSIS else None
        jobs.append((i, base.rule_to_dict(r), internal_mode, cached))

    if not PARALLEL or workers <= 1:
        out = []
        for job in jobs:
            out.append(evaluate_one_worker(job))
            print(f'    eval {len(out):03d}/{len(jobs)} done [{now_s()}]')
        out.sort(key=lambda x: x[0])
        return out

    out = []
    print(f'  parallel eval: workers={workers}, jobs={len(jobs)}')
    with ProcessPoolExecutor(max_workers=workers) as ex:
        futs = [ex.submit(evaluate_one_worker, job) for job in jobs]
        for n, fut in enumerate(as_completed(futs), 1):
            try:
                out.append(fut.result())
            except Exception as e:
                print(f'    eval {n:03d}/{len(jobs)} failed hard: {repr(e)} [{now_s()}]')
            if n % 15 == 0 or n == len(jobs):
                print(f'    eval {n:03d}/{len(jobs)} done [{now_s()}]')
    out.sort(key=lambda x: x[0])
    return out

# ---------------- Diversity Skeleton ----------------

def _vec_distance(a, b):
    n = min(len(a), len(b))
    if n <= 0: return 0.0
    return math.sqrt(sum((float(a[i]) - float(b[i])) ** 2 for i in range(n)) / n)


def load_diversity_skeleton():
    if DIVERSITY_SKELETON_FILE.exists():
        try: return json.loads(DIVERSITY_SKELETON_FILE.read_text(encoding='utf-8'))
        except Exception: return []
    return []


def save_diversity_skeleton(skeleton):
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    atomic_write_json(DIVERSITY_SKELETON_FILE, skeleton, indent=2)


def update_diversity_skeleton(skeleton, results, gen, limit=140):
    existing = {item.get('key') for item in skeleton}
    existing_vecs = [item.get('vector', []) for item in skeleton if item.get('vector')]
    candidates = []
    for score, rule, metrics in results:
        if metrics.get('eval_error') is not None:
            continue
        vec = base.metric_feature_vector(metrics)
        key = rule_hash(rule)
        if key in existing:
            continue
        far = 1.0 if not existing_vecs else min(_vec_distance(vec, v) for v in existing_vecs)
        weird = max(
            metrics.get('in_generation_diversity', 0.0),
            metrics.get('novelty_behavior', 0.0),
            metrics.get('quasi_particle_score', 0.0),
        )
        keep_score = float(score) * 0.015 + far * 55.0 + weird * 25.0
        candidates.append((keep_score, key, score, rule, metrics, vec, far, weird))

    candidates.sort(key=lambda x: x[0], reverse=True)
    for _, key, score, rule, metrics, vec, far, weird in candidates[:20]:
        skeleton.append({
            'key': key, 'generation': gen, 'rule_id': rule.rule_id, 'score': score,
            'class': classify_world(metrics), 'diversity_distance': round(far, 6), 'weirdness': round(weird, 6),
            'vector': vec,
            'metrics': {
                'life': metrics.get('ms_local_life'), 'memory': metrics.get('memory_trace_score'),
                'flow': metrics.get('ms_flow'), 'recovery': metrics.get('cosmic_recovery'),
                'crystal_order': metrics.get('crystal_order'), 'defect_density': metrics.get('defect_density'),
                'quasi_particle_score': metrics.get('quasi_particle_score'),
            },
            'rule': base.rule_to_dict(rule),
        })
    skeleton.sort(key=lambda x: (x.get('weirdness', 0.0), x.get('diversity_distance', 0.0), x.get('score', 0.0)), reverse=True)
    skeleton = skeleton[:limit]
    save_diversity_skeleton(skeleton)
    return skeleton

# ---------------- Checkpoint ----------------

def save_checkpoint(gen, score_mode, population, observer_population, next_id, next_observer_id, best_ever, novelty_archive, diversity_skeleton=None):
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    payload = {
        'completed_generation': gen, 'score_mode': score_mode,
        'population': [base.rule_to_dict(r) for r in population],
        'observer_population': observer_population, 'next_id': next_id, 'next_observer_id': next_observer_id,
        'best_ever': None if best_ever is None else {
            'score': best_ever[0], 'rule': base.rule_to_dict(best_ever[1]), 'metrics': best_ever[2],
        },
        'novelty_archive': list(novelty_archive), 'diversity_skeleton': diversity_skeleton or [],
        'random_state': repr(random.getstate()),
    }
    atomic_write_json(CHECKPOINT_FILE, payload, indent=2)
    print(f'  checkpoint saved securely: {CHECKPOINT_FILE}')


def load_checkpoint(expected_mode):
    if not CHECKPOINT_FILE.exists(): return None
    data = json.loads(CHECKPOINT_FILE.read_text(encoding='utf-8'))
    if data.get('score_mode') != expected_mode:
        print(f'Checkpoint mode mismatch: {data.get("score_mode")} != {expected_mode}')
        return None
    population = [base.rule_from_dict(d) for d in data['population']]
    best = data.get('best_ever')
    best_ever = None
    if best:
        best_ever = (best['score'], base.rule_from_dict(best['rule']), best['metrics'])
    return {
        'start_gen': int(data.get('completed_generation', 0)) + 1,
        'population': population,
        'observer_population': data.get('observer_population') or base.make_observer_population(),
        'next_id': int(data.get('next_id', len(population))),
        'next_observer_id': int(data.get('next_observer_id', base.OBSERVER_COUNT)),
        'best_ever': best_ever,
        'novelty_archive': data.get('novelty_archive', []),
        'diversity_skeleton': data.get('diversity_skeleton', []),
    }

# ---------------- Evolution Loop ----------------

def detailed_console_line(i, rule, score, metrics):
    if metrics.get('eval_error') is not None:
        print(f'  [{i:03d}/{POPULATION}] rule={rule.rule_id:05d} CRASHED score={score:8.1f} error={metrics.get("eval_error")}')
        return

    print(
        f'  [{i:03d}/{POPULATION}] rule={rule.rule_id:05d} score={score:8.3f} '
        f'active={metrics["active"]:.3f} edge={metrics["edge"]:.3f} '
        f'b_act={metrics["boundary_activity"]:.5f} islands={metrics["islands"]} '
        f'nested={metrics.get("nested_score_raw",0):.3f} life={metrics.get("ms_local_life",0):.3f} '
        f'flow={metrics.get("ms_flow",0):.4f} rot={metrics.get("ms_rotation_flow",0):.4f} '
        f'ent={metrics.get("entity_count",0)} trk={metrics.get("persistent_tracks",0)} '
        f'objQ={metrics.get("best_entity_quality",0):.3f} reg={metrics.get("best_region_score",0):.3f} '
        f'rc={metrics.get("region_count",0)} nov={metrics.get("novelty_behavior",0):.3f} '
        f'div={metrics.get("in_generation_diversity",0):.3f} mac={metrics.get("macro_scaffold",0):.1f} '
        f'mem={metrics.get("memory_trace_score",0):.1f} cr={metrics.get("cosmic_recovery",0):.3f} '
        f'xtal={metrics.get("crystal_order",0):.2f} def={metrics.get("defect_density",0):.3f} qp={metrics.get("quasi_particle_score",0):.2f} cache={int(bool(metrics.get("crystal_cache_hit", False)))} '
        f'hum={metrics.get("human_bonus",0):.0f} '
        f'pen={metrics.get("degeneracy_penalty",0):.1f}/{metrics.get("degeneracy_penalty_raw",0):.1f} '
        f'obs={metrics.get("observer_id","-")}:{metrics.get("observer_score",0):.1f}'
    )
    note = metrics.get('observer_note', '')
    if metrics.get('persistent_entity_score', 0.0) > 0.20 or metrics.get('best_entity_quality', 0.0) > 0.25 or metrics.get('best_region_score', 0.0) > 0.18 or metrics.get('best_hotspot_score', 0.0) > 0.20:
        print(f'      observer: {note}')


def run_evolution_v20(score_mode='observer_niches', resume=False):
    global MAIN_PID
    MAIN_PID = os.getpid()
    os.environ['UNIVERSE_SEARCH_MAIN_PID'] = str(MAIN_PID)
    configure_base_paths()
    load_crystal_cache()
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    ATLAS_DIR.mkdir(parents=True, exist_ok=True)

    favorites = base.load_human_favorites()
    favorite_signatures = {base.rule_signature(r) for r in favorites}

    state = load_checkpoint(score_mode) if resume else None
    if state:
        print(f'Resumed from checkpoint at generation {state["start_gen"]}')
        population = state['population']
        observer_population = state['observer_population']
        next_id = state['next_id']
        next_observer_id = state['next_observer_id']
        best_ever = state['best_ever']
        novelty_archive = collections.deque((state['novelty_archive'] or [])[-NOVELTY_ARCHIVE_MAXLEN:], maxlen=NOVELTY_ARCHIVE_MAXLEN)
        diversity_skeleton = state.get('diversity_skeleton') or load_diversity_skeleton()
        start_gen = state['start_gen']
    else:
        observer_population = base.make_observer_population() if score_mode in ('observer_evolution', 'coevolution', 'observer_stability', 'observer_genetics', 'observer_niches') else []
        next_observer_id = OBSERVER_COUNT
        population = [base.make_random_rule(i) for i in range(POPULATION)]
        if favorites:
            print(f'Loaded {len(favorites)} human favorite seed rules')
            for j, fav in enumerate(favorites[:min(len(favorites), POPULATION // 4)]):
                fav.rule_id = j
                population[j] = fav
        next_id = POPULATION
        best_ever = None
        novelty_archive = collections.deque(maxlen=NOVELTY_ARCHIVE_MAXLEN)
        diversity_skeleton = load_diversity_skeleton()
        start_gen = 1

    for gen in range(start_gen, GENERATIONS + 1):
        gen_t0 = time.time()
        print(f'Generation {gen}/{GENERATIONS} mode={score_mode} [{now_s()}]')
        internal_mode = 'hierarchical_novelty' if score_mode in ('hierarchical_novelty', 'observer_evolution', 'coevolution', 'observer_stability', 'observer_genetics', 'observer_niches') else score_mode

        raw = evaluate_population(population, internal_mode, workers=WORKERS)

        results = []
        generation_vectors = []
        for idx, raw_score, rule_dict, metrics in raw:
            rule = base.rule_from_dict(rule_dict)
            score = raw_score

            if metrics.get('eval_error') is not None:
                metrics.update(empty_crystal_metrics('skipped because eval_error'))
                metrics['observer_score'] = -1e9
                metrics['observer_id'] = -1
                metrics['observer_note'] = f'eval failed: {metrics.get("eval_error")}'
                results.append((score, rule, metrics))
                detailed_console_line(idx + 1, rule, score, metrics)
                continue

            if base.rule_signature(rule) in favorite_signatures:
                metrics['human_bonus'] = 28.0
                score += 28.0
            else:
                metrics['human_bonus'] = 0.0

            merge_crystal_into_main_cache(rule, metrics)

            vec = base.metric_feature_vector(metrics)
            novelty_score = base.novelty_from_archive(vec, novelty_archive)
            in_gen_diversity = base.novelty_from_archive(vec, generation_vectors)
            generation_vectors.append(vec)
            metrics['novelty_behavior'] = novelty_score
            metrics['in_generation_diversity'] = in_gen_diversity

            if score_mode in ('observer_evolution', 'coevolution', 'observer_stability', 'observer_genetics', 'observer_niches'):
                obs_scores = [(base.observer_score(o, metrics), o) for o in observer_population]
                obs_scores.sort(key=lambda x: x[0], reverse=True)
                best_obs_score, best_obs = obs_scores[0]
                metrics['observer_score'] = best_obs_score
                metrics['observer_id'] = best_obs.get('id', -1)
                metrics['observer_archetype'] = best_obs.get('archetype', 'unknown')
                gen_pressure = 1.0 - 0.35 * ((gen - 1) / max(1, GENERATIONS - 1))
                score = score * 0.52 + best_obs_score + novelty_score * (base.NOVELTY_BONUS_BASE * 0.55) + in_gen_diversity * (base.DIVERSITY_BONUS_BASE * gen_pressure)
            elif score_mode in ('hierarchical_novelty', 'adaptive_observer', 'cosmic_curator'):
                gen_pressure = 1.0 - 0.35 * ((gen - 1) / max(1, GENERATIONS - 1))
                score = score * 0.70 + novelty_score * base.NOVELTY_BONUS_BASE + in_gen_diversity * (base.DIVERSITY_BONUS_BASE * gen_pressure) + min(metrics.get('macro_scaffold',0), 120) * 0.12
            elif score_mode == 'novelty':
                gen_pressure = 1.0 - 0.35 * ((gen - 1) / max(1, GENERATIONS - 1))
                score = score * 0.62 + novelty_score * 58.0 + in_gen_diversity * (34.0 * gen_pressure)

            if CRYSTAL_DEFECT_ANALYSIS:
                metrics['crystal_defect_bonus'] = metrics.get('quasi_particle_score', 0.0) * CRYSTAL_DEFECT_BONUS
                score += metrics['crystal_defect_bonus']

            if score > -20 or novelty_score > 0.38 or in_gen_diversity > 0.55:
                novelty_archive.append(vec)
            results.append((score, rule, metrics))
            detailed_console_line(idx + 1, rule, score, metrics)

        results.sort(key=lambda x: x[0], reverse=True)
        clean_results = [r for r in results if r[2].get('eval_error') is None]
        if not clean_results:
            print('  all rules failed this generation; saving checkpoint and stopping safely.')
            save_crystal_cache()
            save_checkpoint(gen, score_mode, population, observer_population, next_id, next_observer_id, best_ever, novelty_archive, diversity_skeleton)
            break

        if score_mode in ('coevolution', 'observer_stability', 'observer_niches'):
            observer_population, next_observer_id, truth_by_sig = base.evolve_observers_with_posttest(observer_population, clean_results, next_observer_id, gen)
            for _, r0, m0 in clean_results:
                sig = base.rule_signature(r0)
                if sig in truth_by_sig:
                    m0['post_test_truth'] = truth_by_sig[sig]
            base.save_observers(observer_population)
            lead = observer_population[0]
            print(f'  coevolution observer champion: id={lead.get("id")} arch={lead.get("archetype")} fitness={lead.get("fitness",0):.2f}')
            if score_mode == 'observer_niches':
                base.write_niche_summary(gen, score_mode, clean_results)
        elif score_mode == 'observer_evolution':
            top_metrics = [m for _, _, m in clean_results[:KEEP_TOP]]
            observer_population, next_observer_id = base.evolve_observers(observer_population, top_metrics, next_observer_id)
            base.save_observers(observer_population)

        gen_best = clean_results[0]
        if best_ever is None or gen_best[0] > best_ever[0]:
            best_ever = gen_best

        payload = [{'score': s, 'rule': base.rule_to_dict(r), 'metrics': m} for s, r, m in clean_results[:KEEP_TOP]]
        atomic_write_json(OUT_DIR / f'generation_{gen:02d}_{score_mode}.json', payload, indent=2)
        atomic_write_json(OUT_DIR / f'best_{score_mode}.json', {'score': best_ever[0], 'rule': base.rule_to_dict(best_ever[1]), 'metrics': best_ever[2]}, indent=2)

        add_to_atlas(gen, score_mode, select_atlas_items(clean_results, score_mode))
        diversity_skeleton = update_diversity_skeleton(diversity_skeleton, clean_results, gen)
        save_crystal_cache()
        print(f'  valid results: {len(clean_results)}/{len(results)}')
        print(f'  diversity skeleton: {len(diversity_skeleton)} reps -> {DIVERSITY_SKELETON_FILE}')

        print(f'BEST gen={gen}: rule={gen_best[1].rule_id:05d} score={gen_best[0]:.3f} | best ever={best_ever[1].rule_id:05d} {best_ever[0]:.3f}')
        print(f'  best observer: {gen_best[2].get("observer_note", "no note")}')
        print(f'  generation time: {(time.time() - gen_t0)/60:.1f} min')

        if score_mode == 'observer_niches':
            elite_rules = []
            seen_sigs = set()
            for _, r, _ in clean_results[:max(4, ELITES//2)]:
                sig = base.rule_signature(r)
                if sig not in seen_sigs:
                    elite_rules.append(r); seen_sigs.add(sig)
            for _, (_, r, _) in base.niche_champions(clean_results):
                sig = base.rule_signature(r)
                if sig not in seen_sigs:
                    elite_rules.append(r); seen_sigs.add(sig)
            elites = elite_rules[:max(2, ELITES)]
        else:
            elites = [r for _, r, _ in clean_results[:ELITES]]

        newpop = elites[:]
        while len(newpop) < POPULATION - RANDOM_IMMIGRANTS:
            if len(elites) < 2:
                newpop.append(base.make_random_rule(next_id))
            else:
                a, b = random.sample(elites, 2)
                newpop.append(base.crossover(a, b, next_id))
            next_id += 1
        while len(newpop) < POPULATION:
            newpop.append(base.make_random_rule(next_id)); next_id += 1
        population = newpop

        save_checkpoint(gen, score_mode, population, observer_population, next_id, next_observer_id, best_ever, novelty_archive, diversity_skeleton)

    print('Search complete.')
    if best_ever is not None:
        print(f'Best rule: {best_ever[1].rule_id:05d}, score={best_ever[0]:.3f}')
    else:
        print('No valid best rule was found.')
    print(f'Atlas index: {ATLAS_INDEX_FILE}')


def main():
    mode = sys.argv[1].lower() if len(sys.argv) > 1 else 'help'
    score_mode = sys.argv[2].lower() if len(sys.argv) > 2 else 'observer_niches'
    if score_mode not in base.SCORE_MODES:
        score_mode = 'observer_niches'
    if mode in ('evolve', 'search'):
        try: run_evolution_v20(score_mode, resume=False)
        finally: save_crystal_cache()
    elif mode == 'resume':
        try: run_evolution_v20(score_mode, resume=True)
        finally: save_crystal_cache()
    elif mode == 'view':
        configure_base_paths()
        if base.tk is None:
            print('tkinter is not available. Viewer disabled.')
            return
        root = base.tk.Tk()
        base.Viewer(root)
        root.mainloop()
    else:
        print('Universe Search v2.1.4.1 - parallel crystal defects wrapper')
        print('Put this file next to universe_search_v10_4_observer_niches.py')
        print('Commands:')
        print('  python universe_search_v21_4_1_parallel_crystal.py evolve observer_niches')
        print('  python universe_search_v21_4_1_parallel_crystal.py resume observer_niches')
        print('  python universe_search_v21_4_1_parallel_crystal.py view')
        print(f'Default workers: {WORKERS}')


if __name__ == '__main__':
    main()
