# Universe Search v23 Information

Experimental information-aware version of Universe Search.

This version explores artificial worlds not only by structure, memory,
flow and crystal-like dynamics, but also by early information-oriented
metrics such as persistence, legacy and post-collapse traces.

## Files

-   `universe_search_v23_information.py` --- Main evolutionary search
    script for v23.
-   `universe_search_core.py` --- Core simulation engine.
-   `analyze_results_v241_research_archive.py` --- Analyzer with
    Research Archive support.
-   `universe_search_observer_v13_archive.py` --- Observer with
    Observation Archive support.

## Run evolutionary search

Start a new search:

``` bat
python universe_search_v23_information.py evolve observer_niches
```

Resume from checkpoint:

``` bat
python universe_search_v23_information.py resume observer_niches
```

Open viewer:

``` bat
python universe_search_v23_information.py view
```

Results are saved to:

``` text
universe_search_v23_results/
```

## Analyze results

After the search is complete:

``` bat
python analyze_results_v241_research_archive.py universe_search_v23_results
```

Analyzer creates a non-overwriting research archive:

``` text
universe_search_v23_results/
  analysis/
    experiment_0001/
    experiment_0002/
    latest/
    experiment_index.csv
```

Generated reports may include:

-   `research_summary.md`
-   `information_analysis.md`
-   `correlations.md`
-   `interesting_worlds.md`
-   `next_experiments.md`
-   `experiment.json`

## Observe best world

``` bat
python universe_search_observer_v13_archive.py universe_search_v23_results best --log --events-csv --samples-csv --passport --auto-stop --max-ticks 100000
```

Observer creates:

``` text
universe_search_v23_results/
  observation_logs/
    observation_0001_rule_best/
    observation_0002_rule_XXXXX/
    latest/
    observation_index.csv
```

## Observe a specific rule

``` bat
python universe_search_observer_v13_archive.py universe_search_v23_results 507 --log --events-csv --samples-csv --passport --auto-stop --max-ticks 100000
```

## New in v23

-   Information survival metrics
-   Identity persistence metrics
-   Legacy / post-collapse structure metrics
-   Organism-aware probing
-   Research Archive
-   Observation Archive
-   Improved Analyzer
-   Improved Observer

## Research goal

This version does not attempt to prove artificial life or consciousness.

Its goal is to explore which persistent, adaptive and
information-preserving processes may emerge inside simple artificial
rule spaces using evolutionary search.

