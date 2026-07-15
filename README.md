# Enrichment Pipeline

A small batch pipeline that reads company domains from a file, calls a mock enrichment provider, and writes normalized results plus a run summary. It is designed to be robust against provider flakiness and rate limits, and to avoid silent data loss.

## Prerequisites

- Python 3.10+  
- Node.js 18+

## Setup

```bash
git clone https://github.com/surajkalangi/enrichment-pipeline-solution.git
cd enrichment-pipeline-solution
python3 -m venv .venv && source .venv/bin/activate   # optional
python -m pip install -r requirements.txt
# (optional) set the provider token for non-test environments:
# export PROVIDER_TOKEN=your_token_here
```

## Start the mock provider

```bash
cd starter-kit
node mock-provider.js   # listens on http://localhost:4000
```

Leave this running in a terminal.

## Input

The pipeline reads one domain per line from `starter-kit/domains.csv`, for example:

```text
stripe.com
figma.com
notion.so
domain        # invalid, will be skipped
Stripe.com    # duplicate of stripe.com (case-insensitive)
```

Domains are lowercased, validated for basic syntax, and deduplicated before enrichment. Empty/invalid/duplicate lines are recorded as `skipped` with a reason.

## Run the pipeline

From the project root (with the provider running):

```bash
python3 pipeline_solution.py
```

This will:

- Enrich each valid domain via the mock provider, with per-request timeouts and bounded retries only for transient errors (TEMPORARY, RATE_LIMITED, network issues).
- Write per-domain results as NDJSON to `output.ndjson`.
- Write a run summary as JSON to `summary.json`.

## Output overview

Each NDJSON record includes:

- Pipeline metadata: `domain`, `http_status`, `elapsed_ms`, `provider_status`, `provider_code`, `status` (`enriched_success` / `enriched_failure` / `skipped`), `failure_reason`, `attempts`.
- Normalized enrichment data:
  - `employeeCount_numeric` + `employeeCount_band` (e.g. `1-10`, …, `100,001+`).
  - `industry_list`: always an array of strings.
  - `location`: always `{ "city": ..., "country": ... }`.
  - `foundedYear`: integer or `null`.
  - `annualRevenueUsd`: when available.

`summary.json` contains aggregate counts (total input, skipped, successes, failures, `failure_by_reason`) so an operator can quickly see how many domains succeeded, how many failed, and why.

## Test the mock provider

A small helper script, `client_test.py`, was used during development to exercise the mock API served by `starter-kit/mock-provider.js` and observe how it responds to sample requests.

You can run it from the project root with:

```bash
python3 client_test.py
```

This is useful for quickly validating the provider contract before running the full pipeline.

For design details and trade-offs (stack choice, retry rules, normalization guarantees, and scaling plan), see `DECISIONS.md`.