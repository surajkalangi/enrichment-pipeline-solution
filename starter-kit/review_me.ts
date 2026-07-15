type Company = {
  domain: string;
  name: string;
  employees: number;
  industry: string | string[];
};

const PROVIDER_URL = "http://localhost:4000";
const PROVIDER_TOKEN = "demo-token-abc123";

// REVIEW: OK for local mocks. In real code prefer config/env (e.g. process.env.PROVIDER_TOKEN)
// — avoid checked-in secrets and make test defaults explicit in docs.

/**
 * Enriches an array of domains by calling the mock provider.
 */
export async function enrichDomains(domains: string[]): Promise<Company[]> {
  console.log(`Enriching ${domains.length} domains with token ${PROVIDER_TOKEN}`);

  // REVIEW: Input hygiene is missing.
  // - Normalize (trim + lowercase), validate syntax, and dedupe before calling provider.
  // - Reject or emit a "skipped" record for invalid lines so failures are explicit.

  // REVIEW: Promise.all over the entire domains array creates an unbounded number of
  // concurrent requests. For a handful of domains this is fine, but for large inputs
  // (e.g. 100k domains) this will simultaneously open thousands of connections,
  // likely triggering rate limits, exhausting provider capacity, and crashing the process.
  // Concurrency should be bounded — e.g. via a semaphore or a worker pool that limits
  // in-flight requests to a fixed number (e.g. 20) — so throughput scales safely
  // without overwhelming the provider or the local network stack.
  const results = await Promise.all(
    domains.map(async (domain) => {
      // REVIEW: Infinite loop with no jitter/backoff is unsafe.
      // Replace with bounded attempts, exponential backoff + jitter and respect Retry-After.
      let attempts = 0;
      while (true) {
        attempts += 1;

        try {
          const res = await fetch(`${PROVIDER_URL}/v1/enrich?domain=${domain}`, {
            headers: { Authorization: `Bearer ${PROVIDER_TOKEN}` },
          });

          // REVIEW: Treat 429/5xx as potentially transient but:
          // - Respect Retry-After header when present
          // - Retry should be bounded only for transient errors (e.g. TEMPORARY, RATE_LIMITED) and add jitter between retries
          // - Record a structured failure after attempts are exhausted instead of returning null
          if (res.status === 429 || res.status >= 500) {
            if (attempts >= 3) {
              // REVIEW: Even with a simple cap, we should record failures rather than looping indefinitely.
              return null;
            }
            continue;
          }

          const body: any = await res.json();
          const data = body.data;

          // REVIEW: Do not assume HTTP 200 == success. Inspect provider `status` and `code`.
          // Codes such as NO_MATCH are semantically different from a transient error.

          return {
            domain: data.domain,
            name: data.name,
            // REVIEW: employeeCount normalization: preserve raw value and expose
            // numeric + banded forms after parsing (do not silently truncate).
            employees: parseInt(data.employeeCount), // TODO: normalize before returning
            // REVIEW: Normalize `industry` to `string[]` for consumer simplicity.
            industry: data.industry,
          };
        } catch (e) {
          // REVIEW: Returning null on exception and filtering it out later drops failures silently.
          // The pipeline should return (or rethrow) structured failure records (with domain + error type),
          // or at least log them, to avoid silent data loss.
          return null;
        }
      }
    })
  );

  // REVIEW: Filtering NULL hides failures. Prefer returning structured result
  // objects for success and failure so callers can reconcile and report.
  return results.filter(Boolean) as Company[];
}

// REVIEW (overall): This function is fine as a quick mock demo, but to meet the assignment
// expectations for a robust enrichment pipeline it should:
// - Validate and deduplicate input domains.
// - Use bounded retries with backoff and proper handling of transient vs permanent errors.
// - Expose structured success and failure results for every domain.
// - Normalize messy fields (employeeCount, industry, location) into a consistent schema so
//   downstream consumers don't have to handle provider quirks directly.