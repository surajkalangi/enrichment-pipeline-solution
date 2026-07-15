# Run Summary

## Aggregate counts

- Total input lines: 41
- Total skipped: 5
- Total enriched successes: 33
- Total enriched failures: 3

## Skipped input breakdown

- Invalid domain syntax: 2
  - Examples: `domain`, `not a domain`
- Duplicate domains: 2
  - Example: `stripe.com` (including case variants like `Stripe.com`)
- Empty lines: 1

## Failure breakdown

- `provider_error_NO_MATCH`: 2
  - Domains with no matching company record in the provider.
- `retry_exhausted`: 1
  - Domain that remained in a transient failure state after all retry attempts.

## Brief observations

- All 41 input lines are accounted for as either enriched (success/failure) or skipped with an explicit reason, so there is no silent data loss.
- The majority of domains enriched successfully; failures are dominated by genuine “no match” cases, with a single domain hitting the retry cap and being marked as `retry_exhausted`.