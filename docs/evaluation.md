# Development checks

The parser and workflow tests use synthetic records. They check version ordering, lot boundaries, explicit time zones, saved-work ownership and quote validation. They do not establish retrieval quality on a real procurement collection.

The numeric claim check rejects digits absent from a quoted passage. A copied quote can still support a misleading interpretation. Model assistance is optional and its output needs review.

A separately labelled query set and a populated vector index are required before reporting retrieval scores. No measured relevance or latency result is included in this version.

`evaluation/run_retrieval.py` checks coverage before recording ranks. Its included query file is synthetic. Supply an independently labelled real collection before interpreting any scores.
