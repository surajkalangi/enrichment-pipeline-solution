import time
import requests

BASE_URL = "http://localhost:4000"  
TOKEN = "test-token"              

domains = ["stripe.com", "figma.com"]

for domain in domains:
    url = f"{BASE_URL}/v1/enrich"
    params = {"domain": domain}
    headers = {
        "Authorization": f"Bearer {TOKEN}",      # required auth
        "X-Provider-Version": "2",               # force v2 format
    }

    start = time.perf_counter()
    try:
        resp = requests.get(url, params=params, headers=headers, timeout=10)
        print(resp.__dict__)
        elapsed = (time.perf_counter() - start) * 1000  # ms

        print(f"Domain={domain} | status_code={resp.status_code} | "
              f"elapsed_ms={elapsed:.2f}")

        # Optional: look at provider 'status' field and any error code
        # body = resp.json()
        # print("  provider_status=", body.get("status"), "code=", body.get("code"))
    except requests.RequestException as e:
        elapsed = (time.perf_counter() - start) * 1000
        print(f"Domain={domain} | exception={type(e).__name__} | elapsed_ms={elapsed:.2f}")