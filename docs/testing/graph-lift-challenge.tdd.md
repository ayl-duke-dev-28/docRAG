# Graph-lift challenge TDD evidence

## Source and user journey

No plan file was provided. The journey was derived from the previous release
gap: as a maintainer, I want a reproducible tight-context evaluation where
graph-aware retrieval must outperform lexical retrieval, so the graph's value
is measured rather than inferred from a tied regression set.

## RED / GREEN checkpoints

| Guarantee | RED commit | GREEN commit | Validation |
|---|---|---|---|
| Five source-backed challenge questions exist | `70cf69d` | `bc59563` | `.venv/bin/pytest -q tests/test_evals_loader.py` |
| Eval runs can set a tight context budget with `--top-k` | `c6cb69e` | `be07820` | `.venv/bin/pytest -q tests/test_evals_runner.py` |
| Report comparison can require a minimum graph lift | `78562c8` | `dfd4e4d` | `.venv/bin/pytest -q tests/test_evals_compare.py` |

## Measured result

The public corpus was seeded offline with the regex extractor. Both adapters
ran the same five questions with `top_k=2`:

- Baseline: 2/5, 40%.
- Graph-aware: 5/5, 100%.
- Improvement: +60 percentage points.

CI requires a graph pass rate of at least 80% and an improvement of at least
40 points. The full 20-question public set remains the broad regression floor;
the five-question challenge is specifically the graph-lift proof.
