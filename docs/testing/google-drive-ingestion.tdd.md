# Google Drive ingestion — TDD evidence

## Journey

The slice implements the Week 3 roadmap promise:

> As a lab member, I can connect Google Drive, choose meeting notes, and import
> them through the same chunks-to-graph pipeline used by local documents.

## Guarantees

| # | Behavior | Test type |
|---|---|---|
| 1 | OAuth state values are expiring, one-time, and replay-safe | Unit |
| 2 | Missing OAuth configuration fails before redirect | Unit |
| 3 | Successful code exchange persists owner-only credentials | Unit |
| 4 | Google Docs listing follows Drive pagination | Unit |
| 5 | A selected Google Doc exports as plain text | Unit |
| 6 | OAuth, callback, and listing routes expose the adapter | Integration |
| 7 | Import deduplicates requested ids and reuses `ingest_file` | Integration |

Tests inject fake OAuth flows and Drive services. They do not contact Google or
require real credentials.

## Verification

```text
node --check static/app.js
.venv/bin/pytest -q
```

Result: **137 passed**. The JavaScript syntax check also passed.
