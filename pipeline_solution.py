import time
import json
import requests

from transform_data import normalize_data

from constants import (
    BASE_URL,
    TOKEN,
    INPUT_FILE,
    OUTPUT_FILE,
    DOMAIN_PATTERN,
    MAX_ATTEMPTS,
    BASE_SLEEP_SECONDS,
)

def is_valid_domain(domain: str) -> bool:
    """
    Very simple domain syntax check.
    Not perfect, but enough to catch obvious garbage/empty lines.
    """
    return bool(DOMAIN_PATTERN.match(domain))

# def enrich_domain(domain: str) -> dict:
#     """
#     Call the mock provider for a single domain and return a structured result.
#     """
#     url = f"{BASE_URL}/v1/enrich"
#     params = {"domain": domain}
#     headers = {
#         "Authorization": f"Bearer {TOKEN}",
#         "X-Provider-Version": "2",
#     }

#     start = time.perf_counter()
#     try:
#         resp = requests.get(url, params=params, headers=headers, timeout=5)
#         elapsed_ms = (time.perf_counter() - start) * 1000
#         body = resp.json()
#         provider_status = body.get("status")
#         provider_code = body.get("code")

#         result = {
#             "domain": domain,
#             "http_status": resp.status_code,
#             "elapsed_ms": elapsed_ms,
#             "provider_status": provider_status,
#             "provider_code": provider_code,
#             "data": body.get("data"),
#         }

#         if resp.status_code == 200 and provider_status == "ok":
#             result["status"] = "enriched_success"
#             result["failure_reason"] = None
#         else:
#             result["status"] = "enriched_failure"
#             # coarse reason for now
#             if resp.status_code >= 500:
#                 result["failure_reason"] = "http_5xx"
#             elif provider_status == "error":
#                 result["failure_reason"] = "provider_error"
#             else:
#                 result["failure_reason"] = "unknown_failure"

#         return result

#     except requests.RequestException as e:
#         elapsed_ms = (time.perf_counter() - start) * 1000
#         return {
#             "domain": domain,
#             "http_status": None,
#             "elapsed_ms": elapsed_ms,
#             "error": type(e).__name__,
#             "status": "enriched_failure",
#             "failure_reason": "request_exception",
#         }

def enrich_domain_with_retry(domain: str) -> dict:
    attempts = 0
    last_result = None

    while attempts < MAX_ATTEMPTS:
        attempts += 1
        start = time.perf_counter()
        try:
            resp = requests.get(
                f"{BASE_URL}/v1/enrich",
                params={"domain": domain},
                headers={
                    "Authorization": f"Bearer {TOKEN}",
                    "X-Provider-Version": "2",
                },
                timeout=5,
            )
            elapsed_ms = (time.perf_counter() - start) * 1000
            body = resp.json()
            raw_data = body.get("data")
            normalized_data = normalize_data(raw_data)
            provider_status = body.get("status")
            provider_code = body.get("code")

            result = {
                "domain": domain,
                "http_status": resp.status_code,
                "elapsed_ms": elapsed_ms,
                "provider_status": provider_status,
                "provider_code": provider_code,
                # normalized enrichment
                "data": normalized_data,
                "raw_data": raw_data,
                "attempts": attempts,
            }

            # Success
            if resp.status_code == 200 and provider_status == "ok":
                result["status"] = "enriched_success"
                result["failure_reason"] = None
                return result

            # Error: decide if retryable
            if provider_status == "error":
                if provider_code in ("TEMPORARY", "RATE_LIMITED"):
                    # prepare to retry
                    last_result = result
                    # RATE_LIMITED: respect Retry-After if present
                    if provider_code == "RATE_LIMITED":
                        retry_after = resp.headers.get("Retry-After")
                        sleep_s = float(retry_after) if retry_after else BASE_SLEEP_SECONDS
                    else:
                        # TEMPORARY: simple exponential backoff
                        sleep_s = BASE_SLEEP_SECONDS * (2 ** (attempts - 1))
                    time.sleep(sleep_s)
                    continue  # next attempt
                else:
                    # Non-retryable provider error (e.g. NO_MATCH, MISSING_DOMAIN)
                    result["status"] = "enriched_failure"
                    result["failure_reason"] = f"provider_error_{provider_code or 'unknown'}"
                    return result

            # HTTP-level failures (5xx)
            if resp.status_code >= 500:
                last_result = result
                # treat as retryable until max attempts
                time.sleep(BASE_SLEEP_SECONDS * (2 ** (attempts - 1)))
                continue

            # Fallback: unknown error, no retry
            result["status"] = "enriched_failure"
            result["failure_reason"] = "unknown_failure"
            return result

        except requests.RequestException as e:
            elapsed_ms = (time.perf_counter() - start) * 1000
            last_result = {
                "domain": domain,
                "http_status": None,
                "elapsed_ms": elapsed_ms,
                "error": type(e).__name__,
                "attempts": attempts,
            }
            # treat request exceptions as retryable up to max attempts
            time.sleep(BASE_SLEEP_SECONDS * (2 ** (attempts - 1)))

    # If we get here, retries were exhausted
    if last_result is None:
        last_result = {"domain": domain, "attempts": attempts}
    last_result["status"] = "enriched_failure"
    last_result["failure_reason"] = "retry_exhausted"
    return last_result

def main():
    seen = set()
    stats = {
        "total_input_lines": 0,
        "total_skipped": 0,
        "total_enriched_success": 0,
        "total_enriched_failure": 0,
        "failure_by_reason": {},
    }

    with open(INPUT_FILE, "r") as f_in, open(OUTPUT_FILE, "w") as f_out, \
         open("summary_step2.json", "w") as f_summary:
        for line in f_in:
            stats["total_input_lines"] += 1
            raw = line.strip()
            if not raw:
                # Represent empty input explicitly
                stats["total_skipped"] += 1
                result = {
                    "domain": None,
                    "input_raw": raw,
                    "status": "skipped",
                    "reason": "empty_line",
                }
                f_out.write(json.dumps(result) + "\n")
                print("Skipped empty line")
                continue

            domain = raw.lower()

            if domain in seen:
                stats["total_skipped"] += 1
                result = {
                    "domain": domain,
                    "input_raw": raw,
                    "status": "skipped",
                    "reason": "duplicate_domain",
                }
                f_out.write(json.dumps(result) + "\n")
                print(f"Skipped duplicate domain: {domain}")
                continue

            if not is_valid_domain(domain):
                stats["total_skipped"] += 1
                result = {
                    "domain": domain,
                    "input_raw": raw,
                    "status": "skipped",
                    "reason": "invalid_domain_syntax",
                }
                f_out.write(json.dumps(result) + "\n")
                print(f"Skipped invalid domain syntax: {domain}")
                continue

            seen.add(domain)

            # Normal enrichment path
            result = enrich_domain_with_retry(domain)
            f_out.write(json.dumps(result) + "\n")
            if result["status"] == "enriched_success":
                stats["total_enriched_success"] += 1
            elif result["status"] == "enriched_failure":
                stats["total_enriched_failure"] += 1
                reason = result.get("failure_reason") or "unknown"
                stats["failure_by_reason"][reason] = (
                    stats["failure_by_reason"].get(reason, 0) + 1
                )

        # Write summary statistics
        json.dump(stats, f_summary, indent=2)
        print("Run summary:", stats)

if __name__ == "__main__":
    main()