# Universe Search v23 Information

> ⚠️ Experimental research version.
>
> This version is under active development and may change between experiments.

Universe Search is an experimental framework for exploring emergent behaviour, persistent structures and information dynamics in artificial rule spaces. It is intended as a research platform rather than a proof of artificial life or consciousness.

`v23_information` introduces early information-aware metrics and adds archive systems for analysis and observation runs, so experiments are easier to reproduce and compare later.

## Research workflow

```text
1. Run Universe Search
        ↓
2. Analyze results
        ↓
3. Observe interesting worlds
        ↓
4. Use results to design the next experiment
```

## Files

| File | Purpose |
| --- | --- |
| `universe_search_v23_information.py` | Main evolutionary search script for v23 |
| `universe_search_core.py` | Core simulation engine |
| `analyze_results_v241_research_archive.py` | Analyzer with Research Archive support |
| `universe_search_observer_v13_archive.py` | Observer with Observation Archive support |

## 1. Run evolutionary search

Start a new search:

```bat
python universe_search_v23_information.py evolve observer_niches
```

Resume from checkpoint:

```bat
python universe_search_v23_information.py resume observer_niches
```

Open viewer:

```bat
python universe_search_v23_information.py view
```

Search results are saved to:

```text
universe_search_v23_results/
```

## 2. Analyze results

After the search is complete:

```bat
python analyze_results_v241_research_archive.py universe_search_v23_results
```

The Analyzer creates a non-overwriting Research Archive:

```text
universe_search_v23_results/
  analysis/
    experiment_0001/
    experiment_0002/
    latest/
    experiment_index.csv
```

Generated reports may include:

- `research_summary.md`
- `information_analysis.md`
- `correlations.md`
- `interesting_worlds.md`
- `next_experiments.md`
- `experiment.json`

## 3. Observe best world

Observe the best discovered world:

```bat
python universe_search_observer_v13_archive.py universe_search_v23_results best --log --events-csv --samples-csv --passport --auto-stop --max-ticks 100000
```

The Observer creates a non-overwriting Observation Archive:

```text
universe_search_v23_results/
  observation_logs/
    observation_0001_rule_best/
    observation_0002_rule_XXXXX/
    latest/
    observation_index.csv
```

## 4. Observe a specific rule

Example:

```bat
python universe_search_observer_v13_archive.py universe_search_v23_results 507 --log --events-csv --samples-csv --passport --auto-stop --max-ticks 100000
```

## Output map

```text
Universe Search
        ↓
universe_search_v23_results/

Analyzer
        ↓
analysis/
  experiment_0001/
  latest/
  experiment_index.csv

Observer
        ↓
observation_logs/
  observation_0001_rule_best/
  latest/
  observation_index.csv
```

## New in v23

- Information survival metrics
- Identity persistence metrics
- Legacy and post-collapse structure metrics
- Organism-aware probing
- Research Archive for analysis runs
- Observation Archive for world observations
- Improved Analyzer reports
- Improved Observer passports

## Notes

This version explores what may be possible inside simple artificial rule spaces.

The main question is not whether a world has the highest score, but whether it shows persistent, adaptive or information-preserving processes worth further investigation.
