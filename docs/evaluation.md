# Development checks

These checks were run locally on 29 September 2026. The collection, queries and labels were selected during development. They are not a held-out relevance benchmark or a claim of production reliability.

## Retrieval

The recorded collection contained 644 notices grouped into 626 procedures. All 626 current records had vectors when the evaluation ran. Eight known-item queries tested whether a specified notice appeared near the top of the results. The queries include English descriptions of Czech and Greek notices.

| Method | Expected notice in top 5 | Mean reciprocal rank, top 100 | Median query time |
| --- | ---: | ---: | ---: |
| BM25 | 6 / 8 | 0.688 | 34 ms |
| BM25 + multilingual vectors | 7 / 8 | 0.779 | 88 ms |

These are sequential local timings, not a load test. The labels identify one expected notice per query, so other useful results receive no credit. The example set is small and was chosen after inspecting the collection. The results support testing hybrid retrieval further, but they do not establish general superiority.

The queries, reasons, ranks, returned identifiers and timings are in `evaluation/retrieval.json` and `evaluation/retrieval-results.json`. Run `uv run python evaluation/run_retrieval.py` after a full vector rebuild. The script does not report scores when index counts or vector coverage are incomplete.

## Source and workflow checks

The parser tests include original TED XML for publications 666712-2026 and 666528-2026. The first retains a Czech lot deadline of 3 November 2026 at 11:00 +01:00, and the calendar export expresses it as 10:00 UTC. Historical publications 609722-2026, 634923-2026 and 666528-2026 form a real amendment chain, including a changed lot deadline.

Two Airflow runs completed import and vector indexing. One recovered after an indexing request was interrupted during an application restart. A later import found a multilingual metadata field that exceeded the initial parser's single-language assumption. That run was recorded as partial. The corrected parser imported the affected publication and the workflow succeeded on retry.

Backend tests cover idempotency, historical arrival order, XML entity rejection, malformed records, retries, account ownership, CSRF, CSV formula escaping, quote validation, calendar deadlines and failed index publication. Browser checks exercise login, saved notices, review notes, saved searches, calendar download, mobile layout and logout. The MCP check uses the real stdio protocol.

A separate Compose project with empty database and search volumes passed migration, account creation, source import, indexing, frontend asset loading and search. The main development database was not reused for that check.

## Model assistance

A CPU Qwen2.5 1.5B model answered a question about the Czech Service Desk notice in roughly 36–39 seconds. Its first response supplied no usable claims. A clearer JSON prompt produced a copied passage with an unsupported "3 years" answer. The passage existed, but it did not support that duration.

That failure led to a digit-based numeric check in addition to quote matching, with a regression test for the observed case. This is a development fix, not independent validation of the guard. Unsupported interpretations, translated numbers and misleading but real quotes remain possible. Model output is therefore an optional draft, and excerpts are the default.

A third run, after the parser supplied the structured contract duration, returned the correct 24 months in about 12 seconds. Its wording about the service still needed review. Structured fields are labelled separately from verbatim source passages in the model evidence.

## Remaining limits

- The demonstration imports bounded date windows. It is not a complete or continuously verified copy of TED.
- Only part of the collection has authoritative XML enrichment. Metadata-only records remain labelled, and unknown exact deadlines remain unknown.
- Status describes the latest imported publication. An award for one lot does not establish the outcome of every other lot in the procedure.
- Requirements in external attachments are not downloaded or analysed.
- The local deployment has no availability commitment, distributed indexing coordination or outbound notification service.
