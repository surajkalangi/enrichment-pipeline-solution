# AI_LOG

This file documents where and how I used AI tools during this assignment, and the judgment calls I made on top of their suggestions.

## Tools used

- Perplexity / chat-style AI assistant for:
  - Clarifying the assignment requirements and API behavior.
  - Drafting small code snippets (e.g. initial test client, retry loop skeletons, normalization helpers).
  - Brainstorming alternative designs (sequential vs concurrent, thread pool vs asyncio).

No AI-generated code or text was taken verbatim without review; all changes were inspected and adapted to match the assignment’s constraints and my own design decisions.

## Key moments where I overrode or directed AI

1. **Overall shape of the pipeline**

   - AI suggested several service-style patterns (e.g. building an HTTP microservice around the enrichment logic).
   - I chose a simple CLI-style batch pipeline instead: a single program that reads from a file and writes NDJSON + summary, which fits the 3–4 hour scope and the “batch over 40 domains, design for 100k+” guidance.
   - This was my call to keep infrastructure minimal and focus on robustness, correctness, and observability.

2. **Retry policy and error handling**

   - Early AI suggestions leaned toward generic “retry on error up to N times” without distinguishing provider error codes.
   - After reading `API.md`, I explicitly narrowed retries to transient conditions (`TEMPORARY`, `RATE_LIMITED`, network errors) and treated `NO_MATCH` and `MISSING_DOMAIN` as permanent failures.
   - I also added bounded attempts (max 3) and backoff / `Retry-After` handling, to avoid unbounded loops and hammering the provider.
   - The final retry behavior reflects my judgment based on the provider’s documented semantics, not a generic template.

3. **Data normalization schema**

   - AI helped sketch normalization helpers, but initial ideas were either too loose (passing through raw data) or too complex.
   - I defined a specific, consistent schema for the v2 `data` object:
     - `employeeCount_numeric` + `employeeCount_band` (with well-defined bands from `1-10` up to `100,001+`).
     - `industry_list` always as `string[]`, regardless of whether the provider returns a string or array.
     - `location` always as `{ city, country }`, with country inferred from a small `CITY_TO_COUNTRY` map when missing.
     - `foundedYear` always present as `int | null`.
   - I then adjusted AI-generated code to implement exactly this schema and guarantee consistency for downstream consumers.

4. **Concurrency and scaling plan**

   - AI proposed multiple concurrency approaches (thread pools, asyncio, process pools).
   - I decided to ship a correct sequential implementation (streaming input/output, bounded retries) and document a realistic asyncio + semaphore plan for 100k+ domains in `DECISIONS.md`, rather than rushing in half-finished async code.
   - This reflects a conscious trade-off: favoring a solid, reviewable core over partially implemented concurrency.

5. **Review of `review_me.ts`**

   - AI helped surface potential issues in `starter-kit/review_me.ts` (unbounded `while (true)`, naive 429/5xx handling, `parseInt` on banded employee counts, silent failure dropping).
   - I curated these into a small set of focused `// REVIEW:` comments aligned with my pipeline’s standards:
     - Bounded retries with backoff.
     - Clear transient vs permanent error handling.
     - Input validation and deduplication.
     - Structured success/failure records and consistent data normalization.
   - The final review comments represent my prioritization of issues and my view of what must be fixed before considering the code robust.

## Summary

AI tools mainly accelerated reading, brainstorming, and drafting. The core decisions — stack choice, input hygiene, retry rules, normalization guarantees, sequential vs concurrent processing, and how to review `review_me.ts` — were made deliberately by me based on the assignment requirements and my own experience with data pipelines and flaky external APIs.