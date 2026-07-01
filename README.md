# universe-search
Searching for artificial worlds with persistent structures, memory, flow and crystal-like dynamics using evolutionary algorithms.
# Universe Search

**Universe Search** is an experimental framework for discovering artificial worlds using evolutionary search over continuous cellular automata.

The goal of the project is **not** to reproduce our universe.

Instead, it searches through millions of possible rule sets to discover artificial worlds that exhibit interesting emergent behavior.

---

## What is being searched?

Every rule is evaluated automatically and rewarded for producing behaviors such as:

- persistent structures
- moving entities
- local memory
- coherent flow
- rotating patterns
- nested organization
- self-recovery after perturbation
- crystal-like order
- long-lived defects inside crystals
- behavioral novelty
- diversity between worlds

Evolution continuously generates new rules, selects the most interesting ones, mutates them and repeats the process.

---

## Crystal Defect Analysis

Version 2.1 introduced an additional analysis stage that searches for ordered crystal-like structures and dynamic defects.

Each candidate world is analyzed for:

- crystal order
- repeating lattice periods
- defect density
- defect persistence
- defect motion
- quasi-particle score

These metrics help identify worlds where stable ordered structures coexist with localized dynamic activity.

---

## Atlas

Interesting worlds are automatically stored inside an Atlas.

Each entry includes:

- rule
- metrics
- classification
- preview image
- animated GIF
- observer notes

The Atlas gradually becomes a searchable catalog of discovered artificial worlds.

---

## Evolution Pipeline

```
Random Rules
      │
      ▼
Simulation
      │
      ▼
Metric Extraction
      │
      ▼
Crystal Analysis
      │
      ▼
Novelty Analysis
      │
      ▼
Observer Evaluation
      │
      ▼
Selection
      │
      ▼
Mutation + Crossover
      │
      ▼
Next Generation
```

---

## Current Features

- Evolutionary search
- Multi-objective scoring
- Observer niches
- Novelty search
- Diversity archive
- Crystal defect detection
- Atlas generation
- Automatic checkpointing
- Multiprocessing evaluation
- Resume after interruption
- Atomic save system

---

## Project Status

This is an experimental research project.

The objective is not to prove physical theories, but to explore the space of possible artificial worlds and discover unexpected forms of emergent complexity.

Many discovered worlds are likely to be uninteresting.

Occasionally, evolution produces surprising structures that deserve closer investigation.

---

## Future Directions

Possible future work includes:

- automatic pattern taxonomy
- graph-based interaction analysis
- long-term stability testing
- neural observers
- distributed evolution
- GPU acceleration
- interactive Atlas browser

---
## Running

Start a new evolutionary search:

```bash
python universe_search.py evolve observer_niches
```

Resume from the latest checkpoint:

```bash
python universe_search.py resume observer_niches
```

Open the interactive world viewer:

```bash
python universe_search.py view
```

Show the built-in help:

```bash
python universe_search.py
```
## License

MIT
