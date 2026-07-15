## PR: Data enrichment pipeline

### Overview

This change adds a small, CLI-style data enrichment pipeline that:

- Reads company domains from an input file (`domains.csv`).
- Calls the mock enrichment provider (`/v1/enrich`, v2 responses) with bounded retries.
- Normalizes the provider’s messy v2 data into a consistent schema.
- Writes per-domain results as NDJSON (`output.ndjson`) and a run summary (`summary.json`).
- Ensures there is no silent data loss: every input line is accounted for as enriched or explicitly skipped.

The goal is to demonstrate a robust, operator-friendly, and scale-aware approach within the assignment’s 3–4 hour scope.

---

### Core design

#### 1. Input handling

- Domains are read line-by-line from `domains.csv`.
- Each line is:
  - Stripped of whitespace.
  - Lowercased (DNS hostnames are case-insensitive).
  - Validated with a simple regex to catch obvious invalid syntax (empty lines, no dot, “not a domain”, etc.).
- A `seen` set on normalized domains avoids duplicate enrichment calls (e.g. `stripe.com` and `Stripe.com`).
- Every input line produces an output record:
  - Valid, unique domains → enriched.
  - Empty/invalid/duplicate domains → `status="skipped"` with a specific `reason`.

This satisfies the “no silent data loss” requirement and gives operators visibility into input quality.

#### 2. Provider client and retry behavior

- The client calls the mock provider’s v2 enrich endpoint with:
  - Required headers (Authorization, version).
  - Per-request timeouts to avoid hanging on slow/flaky responses.
- Each call is classified based on both HTTP status and the provider’s `status` and `code` fields:
  - Success: HTTP 200 + `status="ok"`.
  - Failure: HTTP 200 + `status="error"`, HTTP 5xx, or request-level exception.
- Retry policy:
  - **Retryable**: `TEMPORARY`, `RATE_LIMITED`, and network errors (timeouts, connection errors).
  - **Non-retryable**: `NO_MATCH`, `MISSING_DOMAIN`, and other clearly permanent errors.
  - Max attempts per domain: 3.
  - Backoff:
    - For `RATE_LIMITED`, respect `Retry-After` when present.
    - For `TEMPORARY` and network errors, use simple exponential backoff.

If all attempts fail, the domain is marked `status="enriched_failure"` with `failure_reason="retry_exhausted"`. This avoids unbounded loops and makes transient issues and retry exhaustion visible.

#### 3. Data normalization (v2 success responses)

The provider’s v2 `data` object is messy (mixed types, optional fields). To make the output safe for downstream consumers, it is normalized into a consistent `enrichment` schema:

- `name`, `domain`: passed through or `null` when missing.
- `employeeCount_numeric`: integer if the provider gives a single numeric value; otherwise `null`.
- `employeeCount_band`: banded string such as:
  - `1-10`, `11-50`, `51-200`, `201-1,000`, `1,001-5,000`,
  - `5,001-10,000`, `10,001-50,000`, `50,001-100,000`, `100,001+`,
  based on the numeric count or on the lower bound of a banded string (`"1,000-5,000"`).
- `industry_list`: always an array of strings.
  - Single strings are wrapped into a one-element list.
  - Arrays are cleaned into a `string[]`.
- `location`: always an object `{ city, country }`.
  - Strings are treated as `city` with `country` inferred from a small `CITY_TO_COUNTRY` map when possible.
  - Dicts are mapped from common keys (`city`, `name`, `locality`, `country`, `countryCode`) into `city` and `country`.
- `foundedYear`: always present as an integer or `null`.
- `annualRevenueUsd`: passed through when available, otherwise `null`.

**Guarantee:** downstream consumers can rely on:

- `industry_list` always being a `string[]`.
- `location` always having `city` and `country` keys.
- `employeeCount` always being represented in consistent numeric + banded form when possible.
- `foundedYear` always present, even if `null`.

This normalization moves the complexity from consumers into the pipeline where it belongs.

#### 4. Output and run summary

- Per-domain results are written as NDJSON to `output.ndjson`:
  - Fields include: `domain`, `http_status`, `elapsed_ms`, `provider_status`, `provider_code`, `enrichment`, `status` (`enriched_success` / `enriched_failure` / `skipped`), `failure_reason`, and `attempts`.
- A run summary is written to `summary.json`:
  - `total_input_lines`, `total_enriched_success`, `total_enriched_failure`, `total_skipped`.
  - `failure_by_reason` (e.g. `provider_error_NO_MATCH`, `retry_exhausted`).

This gives operators a quick way to understand how many domains succeeded, how many failed, and why, without scanning the entire NDJSON file.

---

### Scaling and concurrency

- The current implementation processes domains sequentially, streaming input/output and bounding retries.
- For larger datasets (e.g. 100k+ domains), the next step would be:
  - Introduce concurrency via `asyncio` and semaphores (e.g. ~20 in-flight requests).
  - Use async sleeps for backoff and `Retry-After`, allowing other domains to be processed while waiting.
  - Optionally batch domains in small groups based on the provider’s token-bucket logic to avoid hammering the API.

I deliberately stopped at a correct sequential implementation, documenting the concurrency plan in `DECISIONS.md`, rather than rushing in partially-complete async code within the 3–4 hour scope.

---

### Review of `starter-kit/review_me.ts`

As part B, `review_me.ts` now includes focused `// REVIEW:` comments highlighting:

- Unbounded `while (true)` retries and naive handling of 429/5xx.
- Ignoring top-level `status` and `code`, which can misclassify application-level errors (e.g. `NO_MATCH`).
- Fragile `employeeCount` parsing via `parseInt` on banded strings.
- Mixed `industry` types (`string | string[]`) without normalization.
- Silent failure dropping via `null` and `filter(Boolean)`.
- Lack of input validation/deduplication and unbounded concurrency via `Promise.all`.

These comments reflect the robustness and consistency standards used in the pipeline and indicate what must change before that code could be considered production-ready.
