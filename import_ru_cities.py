#!/usr/bin/env python3
"""
Import Russian cities from ru.csv to Supabase

Usage:
    python import_ru_cities.py
"""

import os
import csv
import requests
from pathlib import Path

SUPABASE_URL = os.getenv("SUPABASE_URL", "").rstrip("/")
SUPABASE_KEY = os.getenv("SUPABASE_KEY", "")

HEADERS = {
    "apikey": SUPABASE_KEY,
    "Authorization": f"Bearer {SUPABASE_KEY}",
    "Content-Type": "application/json",
}

# Cities to skip (already added)
SKIP_CITIES = {"Moscow", "Voronezh"}


def get_or_create_russia() -> int:
    """Get Russia country ID, create if not exists."""
    # Try to find Russia
    resp = requests.get(
        f"{SUPABASE_URL}/rest/v1/countries",
        headers=HEADERS,
        params={"code": "eq.RU", "select": "id"},
        timeout=15,
    )
    resp.raise_for_status()
    countries = resp.json()

    if countries:
        print(f"✅ Found Russia in database (id={countries[0]['id']})")
        return countries[0]["id"]

    # Create Russia
    print("📍 Creating Russia in countries table...")
    resp = requests.post(
        f"{SUPABASE_URL}/rest/v1/countries",
        headers=HEADERS,
        json={"name": "Russia", "code": "RU", "active": False},  # inactive by default
        timeout=15,
    )
    resp.raise_for_status()
    created = resp.json()
    print(f"✅ Created Russia (id={created[0]['id']})")
    return created[0]["id"]


def import_cities(csv_path: str, country_id: int) -> tuple[int, int]:
    """Import cities from CSV. Returns (success_count, skipped_count)."""
    success = 0
    skipped = 0

    with open(csv_path, 'r', encoding='iso-8859-1') as f:
        reader = csv.DictReader(f, delimiter=';')

        for row in reader:
            city_name = row['city'].strip()

            # Skip already added cities
            if city_name in SKIP_CITIES:
                print(f"  ⏭️  {city_name:25s} — already added, skipping")
                skipped += 1
                continue

            lat = float(row['lat'])
            lng = float(row['lng'])

            # Check if city already exists
            check_resp = requests.get(
                f"{SUPABASE_URL}/rest/v1/cities",
                headers=HEADERS,
                params={"name": f"eq.{city_name}", "select": "id"},
                timeout=15,
            )
            check_resp.raise_for_status()

            if check_resp.json():
                print(f"  ⏭️  {city_name:25s} — already exists, skipping")
                skipped += 1
                continue

            # Insert city
            try:
                resp = requests.post(
                    f"{SUPABASE_URL}/rest/v1/cities",
                    headers=HEADERS,
                    json={
                        "name": city_name,
                        "country_id": country_id,
                        "lat": lat,
                        "lon": lng,
                        "active": False,  # inactive by default
                    },
                    timeout=15,
                )
                resp.raise_for_status()
                print(f"  ✅ {city_name:25s} ({lat:.4f}, {lng:.4f})")
                success += 1
            except Exception as exc:
                print(f"  ❌ {city_name:25s} — {exc}")

    return success, skipped


def main():
    if not SUPABASE_URL or not SUPABASE_KEY:
        print("❌ SUPABASE_URL and SUPABASE_KEY are required.")
        print("   Set them as environment variables.")
        return

    csv_path = Path(__file__).parent / "ru.csv"
    if not csv_path.exists():
        print(f"❌ File not found: {csv_path}")
        return

    print("🇷🇺 Importing Russian cities from ru.csv")
    print("─" * 60)

    # Get or create Russia country
    country_id = get_or_create_russia()

    print("\n📥 Importing cities...")
    print("─" * 60)

    # Import cities
    success, skipped = import_cities(str(csv_path), country_id)

    print("─" * 60)
    print(f"✅ Done: {success} cities added, {skipped} skipped")
    print("\n💡 To activate cities and Russia:")
    print("   1. Open Admin UI: https://dm-ivanov999.github.io/Parcer_weather/")
    print("   2. Go to Countries → toggle Russia to Active")
    print("   3. Go to Cities → toggle cities you want to Active")


if __name__ == "__main__":
    main()
