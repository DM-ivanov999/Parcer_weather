#!/usr/bin/env python3
"""
UV Index Weather Service v2

Reads active cities from Supabase, fetches UV data from Open-Meteo,
and upserts results into Supabase uv_data table.

Usage:
    python uv_india.py              # Fetch all active cities
    python uv_india.py "Mumbai"     # Fetch single city by name

Dependencies:
    pip install requests
"""

import sys
import os
import time
import requests
from datetime import datetime, timezone

SUPABASE_URL = os.getenv("SUPABASE_URL", "").rstrip("/")
SUPABASE_KEY = os.getenv("SUPABASE_KEY", "")

HEADERS = {
    "apikey": SUPABASE_KEY,
    "Authorization": f"Bearer {SUPABASE_KEY}",
    "Content-Type": "application/json",
}


def supabase_enabled() -> bool:
    return bool(SUPABASE_URL and SUPABASE_KEY)


# ============================================================
# SUPABASE — read cities
# ============================================================

def get_active_cities() -> list[dict]:
    """Read active cities from Supabase cities table."""
    resp = requests.get(
        f"{SUPABASE_URL}/rest/v1/cities",
        headers=HEADERS,
        params={"active": "eq.true", "select": "id,name,lat,lon", "order": "name.asc"},
        timeout=15,
    )
    resp.raise_for_status()
    return resp.json()


def get_city_by_name(name: str) -> dict | None:
    """Find a single city by name (case-insensitive)."""
    resp = requests.get(
        f"{SUPABASE_URL}/rest/v1/cities",
        headers=HEADERS,
        params={"name": f"ilike.{name.strip()}", "select": "id,name,lat,lon", "limit": "1"},
        timeout=15,
    )
    resp.raise_for_status()
    rows = resp.json()
    return rows[0] if rows else None


# ============================================================
# OPEN-METEO API (free, no key required)
# ============================================================

# WMO Weather interpretation codes
WMO_CODES = {
    0:  "Clear sky",
    1:  "Mainly clear",
    2:  "Partly cloudy",
    3:  "Overcast",
    45: "Foggy",
    48: "Rime fog",
    51: "Light drizzle",
    53: "Moderate drizzle",
    55: "Dense drizzle",
    61: "Slight rain",
    63: "Moderate rain",
    65: "Heavy rain",
    71: "Slight snow",
    73: "Moderate snow",
    75: "Heavy snow",
    80: "Slight rain showers",
    81: "Moderate rain showers",
    82: "Violent rain showers",
    85: "Slight snow showers",
    86: "Heavy snow showers",
    95: "Thunderstorm",
    96: "Thunderstorm with hail",
    99: "Thunderstorm with heavy hail",
}


def fetch_uv(name: str, lat: float, lon: float, retries: int = 3) -> dict:
    """Fetch UV Index and weather from Open-Meteo with retry."""
    for attempt in range(retries):
        try:
            resp = requests.get("https://api.open-meteo.com/v1/forecast", params={
                "latitude": lat,
                "longitude": lon,
                "current": "uv_index,temperature_2m,relative_humidity_2m,"
                           "weather_code,wind_speed_10m,apparent_temperature",
                "timezone": "auto",
            }, timeout=30)
            resp.raise_for_status()
            data = resp.json()
            break
        except (requests.RequestException, requests.Timeout) as exc:
            if attempt < retries - 1:
                wait = 2 ** attempt
                print(f"  ⚠️  Retry {attempt + 1}/{retries} for {name} after {wait}s: {exc}")
                time.sleep(wait)
            else:
                raise

    current = data["current"]
    uv = current["uv_index"]

    if uv <= 2:
        uv_desc = "Low"
    elif uv <= 5:
        uv_desc = "Moderate"
    elif uv <= 7:
        uv_desc = "High"
    elif uv <= 10:
        uv_desc = "Very High"
    else:
        uv_desc = "Extreme"

    return {
        "uv_index":     uv,
        "uv_desc":      uv_desc,
        "temperature":  current["temperature_2m"],
        "feels_like":   current["apparent_temperature"],
        "humidity":     current["relative_humidity_2m"],
        "wind_speed":   current["wind_speed_10m"],
        "weather_desc": WMO_CODES.get(current.get("weather_code", -1), "Unknown"),
        "timestamp":    datetime.now(timezone.utc).isoformat(),
    }


# ============================================================
# SUPABASE — upsert UV data
# ============================================================

def upsert_uv_data(city_id: int, data: dict) -> None:
    """Upsert UV data for a city (one row per city, overwritten each time)."""
    resp = requests.post(
        f"{SUPABASE_URL}/rest/v1/uv_data?on_conflict=city_id",
        headers={
            **HEADERS,
            "Prefer": "resolution=merge-duplicates",
        },
        json={
            "city_id":      city_id,
            "uv_index":     data["uv_index"],
            "uv_desc":      data["uv_desc"],
            "temperature":  data["temperature"],
            "feels_like":   data["feels_like"],
            "humidity":     data["humidity"],
            "wind_speed":   data["wind_speed"],
            "weather_desc": data["weather_desc"],
            "updated_at":   data["timestamp"],
        },
        timeout=15,
    )
    resp.raise_for_status()


# ============================================================
# MAIN
# ============================================================

def process_city(city: dict) -> dict:
    """Fetch and save UV data for a single city. Returns weather data."""
    data = fetch_uv(city["name"], city["lat"], city["lon"])
    upsert_uv_data(city["id"], data)
    return data


def main():
    if not supabase_enabled():
        print("❌ SUPABASE_URL and SUPABASE_KEY are required.")
        print("   Set them as environment variables or in .env file.")
        sys.exit(1)

    # Single city mode: python uv_india.py "Mumbai"
    if len(sys.argv) > 1:
        city_name = sys.argv[1]
        city = get_city_by_name(city_name)
        if not city:
            print(f"❌ City '{city_name}' not found in database.")
            print("   Add it via Admin UI or Supabase Dashboard.")
            sys.exit(1)
        cities = [city]
    else:
        # Batch mode: fetch all active cities
        cities = get_active_cities()
        if not cities:
            print("⚠️  No active cities found. Add cities via Admin UI.")
            sys.exit(0)

    print(f"☀️  UV Weather Service — {len(cities)} cities")
    print("─" * 50)

    success_count = 0
    failed = []

    for city in cities:
        try:
            data = process_city(city)
            print(f"  ✅ {city['name']:15s}  UV {data['uv_index']:4.1f} ({data['uv_desc']:9s})  {data['temperature']}°C  {data['weather_desc']}")
            success_count += 1
        except Exception as exc:
            print(f"  ❌ {city['name']:15s}  {exc}")
            failed.append(city["name"])
        time.sleep(2)

    print("─" * 50)
    print(f"✅ Done: {success_count}/{len(cities)} cities updated")
    if failed:
        print(f"❌ Failed: {', '.join(failed)}")

    # Exit with error only if ALL cities failed
    if success_count == 0 and len(cities) > 0:
        sys.exit(1)


if __name__ == "__main__":
    main()
