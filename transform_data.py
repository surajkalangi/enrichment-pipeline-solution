from typing import Any, Dict, List, Optional

from constants import CITY_TO_COUNTRY, EMPLOYEE_BANDS

def _band_for_employee_count(n: Optional[int]) -> Optional[str]:
    if n is None:
        return None
    for low, high, label in EMPLOYEE_BANDS:
        if low <= n <= high:
            return label
    # Option: for counts outside defined bands, you can return None or a catch-all
    return None

def _normalize_employee_count(raw: Any) -> Dict[str, Any]:
    """
    Normalize employeeCount.

    - employeeCount_numeric: int if we can interpret raw as a single number; else None.
    - employeeCount_band: banded string ['1-10', '11-50', '51-200', '201-1,000', '1,001-5,000'] if applicable; else None.
    """
    result = {
        "employeeCount_raw": raw,
        "employeeCount_numeric": None,
        "employeeCount_band": None,
    }

    if raw is None:
        return result

    # If already an int, treat as numeric
    if isinstance(raw, int):
        result["employeeCount_numeric"] = raw
        result["employeeCount_band"] = _band_for_employee_count(raw)
        return result

    # If it's a string, try to parse band "1,000-5,000" or single number "1200"
    if isinstance(raw, str):
        s = raw.replace(",", "").strip()
        if "-" in s:
            # Band like "1000-5000"
            # We keep raw and just compute band label if it matches one of our canonical bands
            try:
                low_str, high_str = s.split("-", 1)
                low = int(low_str)
                high = int(high_str)
                # Use band label matching our known ranges
                band = _band_for_employee_count(low)
                result["employeeCount_band"] = band
            except ValueError:
                # Non-parsable band; leave numeric/band as None
                pass
        else:
            # Single number string
            try:
                n = int(s)
                result["employeeCount_numeric"] = n
                result["employeeCount_band"] = _band_for_employee_count(n)
            except ValueError:
                # Not a number; keep raw only
                pass

    return result

def _normalize_industry(raw: Any) -> List[str]:
    """
    Normalize industry into a list of strings.

    - If raw is a string: return [raw].
    - If raw is a list/tuple: return a list of strings.
    - Else: return [].
    """
    if raw is None:
        return []
    if isinstance(raw, str):
        return [raw.strip()] if raw.strip() else []
    if isinstance(raw, (list, tuple)):
        out = []
        for item in raw:
            if isinstance(item, str):
                s = item.strip()
                if s:
                    out.append(s)
        return out
    return []

def _normalize_location(raw: Any) -> Dict[str, Optional[str]]:
    """
    Normalize location into an object with city and country.

    - Always return {"city": ..., "country": ...}.
    - If raw is a string: treat it as city, infer country from CITY_TO_COUNTRY if possible.
    - If raw is a dict: look for city/country keys, fall back to a generic "city" or "name".
    """
    result = {"city": None, "country": None}

    if raw is None:
        return result

    if isinstance(raw, str):
        city = raw.strip()
        result["city"] = city or None
        if city:
            result["country"] = CITY_TO_COUNTRY.get(city)
        return result

    if isinstance(raw, dict):
        # Try common key names
        city = raw.get("city") or raw.get("name") or raw.get("locality")
        country = raw.get("country") or raw.get("countryCode")
        if isinstance(city, str):
            city = city.strip()
        else:
            city = None
        if isinstance(country, str):
            country = country.strip()
        else:
            country = None

        result["city"] = city or None

        if country:
            result["country"] = country
        elif city:
            # If country missing, try inference from city
            result["country"] = CITY_TO_COUNTRY.get(city)

        return result

    # Other types: leave as unknown
    return result

def _normalize_founded_year(raw: Any) -> Optional[int]:
    """
    Normalize foundedYear to an int or None, always present in the output.
    """
    if raw is None:
        return None
    if isinstance(raw, int):
        return raw
    if isinstance(raw, str):
        s = raw.strip()
        try:
            return int(s)
        except ValueError:
            return None
    return None

def _normalize_annual_revenue(raw: Any) -> Optional[float]:
    """
    Normalize annualRevenueUsd to a float or None, always present in the output.
    """
    if raw is None:
        return None
    if isinstance(raw, (int, float)):
        return float(raw)
    if isinstance(raw, str):
        s = raw.strip().replace(",", "")
        try:
            return float(s)
        except ValueError:
            return None
    return None

def normalize_data(raw: Dict[str, Any]) -> Dict[str, Any]:
    """
    Normalize the provider's v2 success data into a consistent schema.

    - Preserves key fields: name, domain.
    - Normalizes employeeCount, industry, location, foundedYear as per the agreed schema.
    - Keeps a copy of the raw data for reference.
    """
    if raw is None:
        raw = {}

    # Basic fields (pass through as-is if present)
    name = raw.get("name")
    domain = raw.get("domain")

    employee_norm = _normalize_employee_count(raw.get("employeeCount"))
    industry_norm = _normalize_industry(raw.get("industry"))
    location_norm = _normalize_location(raw.get("location"))
    founded_year_norm = _normalize_founded_year(raw.get("foundedYear"))
    annual_revenue_norm = _normalize_annual_revenue(raw.get("annualRevenueUsd"))

    return {
        "name": name,
        "domain": domain,
        # Employee count normalization
        "employeeCount_numeric": employee_norm["employeeCount_numeric"],
        "employeeCount_band": employee_norm["employeeCount_band"],
        "employeeCount_raw": employee_norm["employeeCount_raw"],
        # Industry normalization
        "industry_list": industry_norm,
        # Location normalization (city + country only)
        "location": location_norm,  # {"city": ..., "country": ...}
        # Founded year
        "foundedYear": founded_year_norm,
        "annualRevenueUsd": annual_revenue_norm,
    }