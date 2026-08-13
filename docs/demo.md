# LabGraph 90-second demo

## Reproduce the demo

```bash
demo_data_dir="$(mktemp -d)"
OPENAI_API_KEY='' LABGRAPH_EXTRACTOR=regex \
  .venv/bin/python scripts/seed_public_corpus.py --data-dir "$demo_data_dir"

OPENAI_API_KEY='' LABGRAPH_EXTRACTOR=regex \
LABGRAPH_DATA_DIR="$demo_data_dir" \
LABGRAPH_DB_PATH="$demo_data_dir/labgraph.sqlite3" \
  .venv/bin/uvicorn app:app --port 8000
```

Open `http://127.0.0.1:8000`.

## Recording script

1. **0:00–0:15 — corpus readiness.** Show ten documents, upload/Drive source
   labels, graph entity-kind counts, and document graph contributions.
2. **0:15–0:35 — ask.** Submit: “What did Alex Liu recommend for training
   stability, and where was that choice made?” Show the staged query status.
3. **0:35–1:05 — inspect.** Walk the ordered graph trace from Alex Liu through
   the report and methods to the March team sync. Open one edge disclosure and
   point out provenance chunk IDs.
4. **1:05–1:20 — verify.** Expand the first two sources and show their graph
   evidence labels. Note that later sources remain collapsed.
5. **1:20–1:30 — proof.** Show the checked baseline and graph eval reports and
   the CI no-regression gate.

Record at 1440×900 or larger, keep the browser zoom at 100%, and avoid showing
an `.env` file or credentials.

## Checked demo assets

The repository includes browser-verified screenshots and a silent 12-second
MP4 overview in `docs/assets`. Rebuild the MP4 on macOS after refreshing the
three screenshots:

- [Corpus workspace](assets/demo-corpus.png)
- [Graph trace](assets/demo-trace.png)
- [Full answer evidence](assets/demo-answer.png)
- [12-second MP4 overview](assets/labgraph-demo.mp4)

```bash
swift scripts/build_demo_video.swift
```
