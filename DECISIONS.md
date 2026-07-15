# DECISIONS

This focuses on the main judgment calls: what I built, what I skipped, and why.

## Stack and overall shape

- Built a small CLI‑style batch pipeline in Python 3 using `requests` and the standard library.
- The pipeline reads domains from a file, enriches them via the mock provider, and writes NDJSON per‑domain plus a JSON run summary.
- I intentionally skipped building a long‑running service or adding external queue/worker infrastructure; within 3–4 hours it’s more valuable to get correctness, robustness, and clear output right.

## Input handling and domain hygiene

**Decision:** Validate and account for every line in `domains.csv` before enrichment.

- Each line is stripped of whitespace and normalized to lowercase (DNS hostnames are case‑insensitive).
- A simple regex detects clearly invalid domain syntax (empty lines, “not a domain”, plain words without a dot).
- A `seen` set on the normalized domain detects duplicates (e.g. `stripe.com` and `Stripe.com`).
- Every input line produces an output record:
  - Valid, unique domains → enriched.
  - Empty, invalid, or duplicate domains → `status="skipped"` with a specific `reason`.

**Why:** This guarantees there is no silent data loss; downstream consumers and operators can see exactly what happened to each input line.

## Provider behavior, success/failure rules, and retries

**Decision:** Classify results based on both HTTP status and provider body, and retry only transient failures.

- Observed behavior:
  - HTTP 200 responses with latency from ~90 ms to >3 s.
  - Errors signaled by `status="error"` and codes such as `NO_MATCH`, `TEMPORARY`, `RATE_LIMITED`.
  - Occasional HTTP 5xx and potential timeouts.
- Status rules:
  - `enriched_success`: HTTP 200 and provider body indicates success (e.g. `status="ok"`).
  - `enriched_failure`: HTTP 200 with `status="error"`, any HTTP 5xx, or request‑level exception.
  - `skipped`: input issues (empty, invalid syntax, duplicate) before contacting the provider.
- Retry policy:
  - **Retryable:** `TEMPORARY`, `RATE_LIMITED`, and transport‑level errors (timeouts, connection errors).
  - **Non‑retryable:** `NO_MATCH`, `MISSING_DOMAIN`, and other clearly permanent error codes.
  - Max attempts per domain: 3, with simple backoff:
    - Respect `Retry-After` on `RATE_LIMITED` when present.
    - Exponential backoff for `TEMPORARY` and network errors.
  - If all attempts fail, the domain is marked as `status="enriched_failure"` with `failure_reason="retry_exhausted"`.

**Why:** Retrying only transient failures avoids wasting time and provider capacity on cases that are guaranteed not to succeed (e.g. `NO_MATCH`), while still giving flaky or rate‑limited cases a bounded chance to recover.

## Data normalization and consistency guarantees

**Decision:** Normalize the v2 `data` object into a fixed schema with consistent types, so downstream consumers do not have to handle provider quirks.

For each successful enrichment, the pipeline produces an `enrichment` object with:

- `name`: passed through from provider, or `null` when missing.
- `domain`: passed through from provider, or `null` when missing.
- `employeeCount_numeric`: an integer if the provider gave a single numeric employee count (e.g. `1200` or `"1200"`); otherwise `None`.
- `employeeCount_band`: a banded string such as `'1-10'`, `'11-50'`, …, `'100,001+'` chosen based on `employeeCount_numeric` or the lower bound of a banded string like `"1,000-5,000"`
- `employeeCount_raw`: Raw value preserved for debuggability.
- `industry_list`: always a list of strings:
  - If the provider returns a single string, it becomes `[string]`.
  - If it returns an array, it becomes a cleaned list of strings.
  - If missing or unparseable, it is `[]`.
- `location`: always an object with `{"city": ..., "country": ...}`:
  - If the provider returns a string, it is treated as `city`, and `country` is inferred from a `CITY_TO_COUNTRY` map when possible.
  - If the provider returns a dict, common keys (`city`, `name`, `locality`, `country`, `countryCode`) are mapped into `city` and `country`, with city‑based inference for country if needed.
  - If missing or unparseable, both fields are `None`.
- `foundedYear`: always present as an integer or `null`:
  - If the provider returns an integer or numeric string, it is stored as an `int`.
  - If missing or unparseable, it is `null`.
- `annualRevenueUsd`: passed through from the provider when present; otherwise `null` (or omitted depending on the raw shape).

**Guarantee:** Downstream consumers can rely on:

- `industry_list` always being an array of strings,
- `location` always being an object with `city` and `country` keys,
- `employeeCount` always being represented in a consistent numeric + banded form when possible,
- `foundedYear` always present as an integer or `null`.

They do not need to handle mixed types (string vs array, object vs string) or missing keys themselves; that normalization is done inside the pipeline.

## Output format and run summary

**Decision:** Use NDJSON for per‑domain output and a compact JSON summary.

- NDJSON per‑domain:
  - One JSON object per line, including fields like `domain`, `http_status`, `elapsed_ms`, `provider_status`, `provider_code`, `enrichment`, `status`, `failure_reason`, and `attempts`.
  - Chosen because it supports streaming writes and is easy to inspect with standard tools.
- Run summary JSON:
  - Counts: `total_input_lines`, `total_enriched_success`, `total_enriched_failure`, `total_skipped`.
  - `failure_by_reason` (e.g. `provider_error_NO_MATCH`, `retry_exhausted`).

**Why:** This makes it easy for an operator or downstream process to see how many domains succeeded, how many failed, and why, without scanning the whole NDJSON file; and it keeps the per‑domain output structurally consistent.

## Concurrency, scaling, and what I did *not* build

The assignment says: test against ~40 domains, but design as if the input could be 100k+; you don’t need to actually run 100k. I interpreted that as:

- The pipeline should be logically safe for large inputs (bounded memory, bounded retries, clear failure behavior).
- Within 3–4 hours, it is acceptable to implement a correct sequential version and describe a realistic concurrency plan.

**Current implementation:**

- Processes domains sequentially.
- Streams input and output line‑by‑line, avoiding large in‑memory collections.
- Caps retries per domain, so work per domain is bounded.

**Design for 100k+ (future work):**

- Introduce concurrency using `asyncio` and semaphores:
  - Limit in‑flight requests (e.g. 20 concurrent domains) to balance throughput and provider capacity.
  - Use async sleeps for retry backoff and `Retry-After`, so other domains can be processed while waiting to retry.
- Potentially use small batches informed by the provider’s observed rate-limited behavior and the API documentation, rather than hammering the API continuously.

I chose not to implement the full async layer in the initial version to avoid half‑finished concurrency code and keep the pipeline’s validation, classification, retry, normalization, and summary behavior clear and reviewable.

## Use of AI tools and my judgment

I used AI tools during this assignment to speed up reading the API docs, draft small code snippets (e.g. initial retry loops and normalization helpers), and propose alternative designs (thread pools vs asyncio). In each case, I treated the AI as a suggestion source:

- I chose a simple CLI pipeline over a more complex service, despite AI suggesting service patterns.
- I narrowed the retry policy to TEMPORARY/RATE_LIMITED/network errors based on the provider docs, not just generic “retry all errors” examples.
- I designed the normalization schema (numeric+banded employeeCount, industry_list, location {city, country}, foundedYear int/null) and adjusted AI‑generated code to match those guarantees.

The final pipeline behavior (validation, retries, normalization, summary, and concurrency plan) reflects my decisions rather than blindly accepting tool output.