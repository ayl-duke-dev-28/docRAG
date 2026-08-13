# Retrieval, eval, and corpus UI TDD evidence

## Source and journeys

No plan file was provided. The work implements these user journeys:

- As a researcher, I can reproduce the public multi-source evaluation offline.
- As the retrieval pipeline, I can expand ranked chunk seeds through the graph
  even when a question does not name a complete graph path.
- As a maintainer, I can reject a graph-aware score below the release floor or
  below the baseline score.
- As a user, I can see document origin, graph contribution, staged query
  progress, and accessible source disclosures.

## RED / GREEN checkpoints

| Guarantee | RED commit | GREEN commit | Validation |
|---|---|---|---|
| Bundled eval contains 20 questions backed by checked-in files | `61f1ea2` | `e24ad42` | `.venv/bin/pytest -q tests/test_evals_loader.py` |
| Vector-derived graph neighborhoods promote connected provenance | `3689314` | `f5fdc3a` | `.venv/bin/pytest -q tests/test_graph_aware_retrieval.py tests/test_labgraph_seed.py` |
| Baseline and graph JSON reports have a no-regression gate | `1ba76fb` | `b49fcae` | `.venv/bin/pytest -q tests/test_evals_compare.py` |
| Public corpus seeding creates both SQLite databases | `fba488c` | `84c842d` | `.venv/bin/pytest -q tests/test_public_corpus_seed.py` |
| Document API exposes source and graph contribution metadata | `27ec9e0` | `d633fb3` | focused API and Drive integration tests |
| Corpus and answer UI follows the disclosure/status contract | `9aab9c7`, `9ebfc73` | `ced9eaf` | static contract tests, retrieval tests, and `node --check static/app.js` |
| Regex extraction does not turn document titles into false people | `6eb6b08` | `74e4cf6` | `.venv/bin/pytest -q tests/test_labgraph_extract.py` and browser trace verification |
| Mobile layout puts the query composer before answers and corpus controls | `4f0b9b4` | `87e3ca0` | static contract test and 375×812 browser screenshot |

## Final verification

- `.venv/bin/pytest -q` — 158 passed.
- `node --check static/app.js` — passed.
- Offline public eval — baseline 20/20; graph-aware 20/20.
- `python -m evals.compare ... --min-graph-pass-rate 0.75` — passed at
  baseline 100%, graph 100%, improvement +0%.

## Coverage and known gap

The existing CI command enforces at least 80% combined coverage for `evals`
and `labgraph`. The public set is intentionally small and deterministic. Its
current baseline score is already 100%, so it proves reproducibility and
guards regressions but does not yet prove graph lift. A harder second set of
human-authored paraphrases is the next evaluation-quality improvement.
