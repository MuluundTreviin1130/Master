# Paper-library cache

This directory stores reusable, source-bound extraction artifacts for the
review-paper evidence audits.

`unified_pdf_text/` contains one JSON file per matched cite key. A cache entry
is reused only when the PDF path, file size, modification time, and requested
page limit still match. Delete an individual entry or run the unified audit
with `--refresh-cache` when its source PDF must be re-extracted.

The cache contains text only. Scientific assignments remain in the auditable
CSV outputs next to the runners and must not be inferred from cache presence.
