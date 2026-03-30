# Sources and third-party components

Procurement records come from TED, published by the Publications Office of the European Union. Original notice links, publication identifiers and source checksums are retained. See the [TED legal notice](https://ted.europa.eu/en/legal-notice), [Search API documentation](https://docs.ted.europa.eu/api/latest/search.html) and [eForms schema](https://docs.ted.europa.eu/eforms/latest/schema/all-in-one.html).

TED permits reuse of its notices unless otherwise indicated. Metadata is made available under CC0. This does not grant a blanket licence to attachments hosted on third-party procurement portals. Noticeboard links to those documents but does not bundle them. The included XML fixtures are source notices for parser tests, not synthetic procurement examples.

Application dependencies retain their own licences. Python dependency versions are recorded in `uv.lock`, and frontend versions are in `frontend/package-lock.json`. Principal components include Django (BSD), PostgreSQL (PostgreSQL Licence), OpenSearch and Airflow (Apache 2.0), React (MIT), FastEmbed (Apache 2.0) and the MCP Python SDK (MIT).

The optional multilingual embedding model is [paraphrase-multilingual-MiniLM-L12-v2](https://huggingface.co/sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2), distributed under Apache 2.0. FastEmbed downloads a quantized ONNX conversion. The model is not bundled in the source export. The optional Qwen2.5 1.5B model is also Apache 2.0 and is not bundled.

IBM Plex Sans is distributed by IBM under the SIL Open Font License and bundled through `@fontsource/ibm-plex-sans`. Its licence is included in `frontend/public/font-license.txt`.

Public implementations such as BidPilot and OpenTradeIntel informed feasibility research. No source code from those projects is included in this implementation.
