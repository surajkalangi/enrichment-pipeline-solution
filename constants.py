import re
from pathlib import Path

# Configuration/constants used across the pipeline
BASE_URL = "http://localhost:4000"
TOKEN = "test-token"

# Use project-relative paths so the code is portable across machines
INPUT_FILE = str(Path(__file__).parent / "starter-kit" / "domains.csv")
OUTPUT_FILE = str(Path(__file__).parent / "results_step2.ndjson")

DOMAIN_PATTERN = re.compile(
    r"^(?=.{1,253}$)(?!\-)([A-Za-z0-9\-]{1,63}\.)+[A-Za-z]{2,}$"
)

MAX_ATTEMPTS = 3
BASE_SLEEP_SECONDS = 1.0

CITY_TO_COUNTRY = {
    "Austin": "US",
    "New York": "US",
    "London": "GB",
    "Berlin": "DE",
    "Paris": "FR",
    "Toronto": "CA",
    "Singapore": "SG",
    "Sydney": "AU",
    "Tokyo": "JP",
    "San Francisco": "US",
    "Seattle": "US",
    "Chicago": "US",
    "Boston": "US",
    "Vancouver": "CA",
    "Melbourne": "AU",
}

EMPLOYEE_BANDS = [
    (1, 10, "1-10"),
    (11, 50, "11-50"),
    (51, 200, "51-200"),
    (201, 1000, "201-1,000"),
    (1001, 5000, "1,001-5,000"),
    (5001, 10000, "5,001-10,000"),
    (10001, 50000, "10,001-50,000"),
    (50001, 100000, "50,001-100,000"),
    (100001, float("inf"), "100,001+"),
]
