#!/usr/bin/env python3
"""
UV Index MVP — бесплатно, без ключа, без регистрации
Источник: Open-Meteo API (open-source)

Использование:
    python uv_india.py
    python uv_india.py "Mumbai"
    python uv_india.py "Delhi"
    python uv_india.py "Bangalore"

Зависимости:
    pip install requests
"""

import sys
import sqlite3
import os
import requests
from datetime import datetime
from pathlib import Path

# ============================================================
# ГОРОДА ИНДИИ (координаты) — добавляйте свои
# ============================================================

CITIES = {
    "Delhi":        {"lat": 28.6139, "lon": 77.2090},
    "Mumbai":       {"lat": 19.0760, "lon": 72.8777},
    "Bangalore":    {"lat": 12.9716, "lon": 77.5946},
    "Hyderabad":    {"lat": 17.3850, "lon": 78.4867},
    "Chennai":      {"lat": 13.0827, "lon": 80.2707},
    "Kolkata":      {"lat": 22.5726, "lon": 88.3639},
    "Pune":         {"lat": 18.5204, "lon": 73.8567},
    "Ahmedabad":    {"lat": 23.0225, "lon": 72.5714},
    "Jaipur":       {"lat": 26.9124, "lon": 75.7873},
    "Goa":          {"lat": 15.2993, "lon": 74.1240},
    "Lucknow":      {"lat": 26.8467, "lon": 80.9462},
    "Chandigarh":   {"lat": 30.7333, "lon": 76.7794},
    "Kochi":        {"lat":  9.9312, "lon": 76.2673},
    "Varanasi":     {"lat": 25.3176, "lon": 82.9739},
    "Agra":         {"lat": 27.1767, "lon": 78.0081},
    "Surat":        {"lat": 21.1702, "lon": 72.8311},
    "Indore":       {"lat": 22.7196, "lon": 75.8577},
}

DEFAULT_CITY = "Delhi"
DB_PATH = Path(__file__).parent / "uv_data.db"
SUPABASE_URL = os.getenv("SUPABASE_URL", "").rstrip("/")
SUPABASE_KEY = os.getenv("SUPABASE_KEY", "")
SUPABASE_TABLE = os.getenv("SUPABASE_TABLE", "uv_index")


# ============================================================
# OPEN-METEO API (бесплатно, без ключа)
# ============================================================

def fetch_uv(city: str) -> dict:
    """Запрашивает UV Index и погоду через Open-Meteo."""

    city_title = city.strip().title()

    if city_title not in CITIES:
        print(f"⚠️  Город '{city}' не найден в списке.")
        print(f"   Доступные: {', '.join(sorted(CITIES.keys()))}")
        print(f"   Добавьте координаты в словарь CITIES в скрипте.")
        sys.exit(1)

    coords = CITIES[city_title]

    response = requests.get("https://api.open-meteo.com/v1/forecast", params={
        "latitude":  coords["lat"],
        "longitude": coords["lon"],
        "current":   "uv_index,temperature_2m,relative_humidity_2m,"
                     "weather_code,wind_speed_10m,apparent_temperature",
        "timezone":  "Asia/Kolkata",
    })
    response.raise_for_status()
    data = response.json()

    current = data["current"]

    # Описание UV уровня
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

    # Описание погоды по WMO коду
    weather_desc = WMO_CODES.get(current.get("weather_code", -1), "Unknown")

    return {
        "timestamp":    datetime.now().isoformat(),
        "city":         city_title,
        "uv_index":     uv,
        "uv_desc":      uv_desc,
        "temperature":  current["temperature_2m"],
        "feels_like":   current["apparent_temperature"],
        "humidity":     current["relative_humidity_2m"],
        "wind_speed":   current["wind_speed_10m"],
        "weather_desc": weather_desc,
    }


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


# ============================================================
# БАЗА ДАННЫХ SQLite
# ============================================================

def init_db():
    conn = sqlite3.connect(DB_PATH)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS uv_index (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp    TEXT NOT NULL,
            city         TEXT NOT NULL,
            uv_index     REAL,
            uv_desc      TEXT,
            temperature  REAL,
            feels_like   REAL,
            humidity     INTEGER,
            wind_speed   REAL,
            weather_desc TEXT
        )
    """)
    conn.commit()
    return conn


def supabase_enabled() -> bool:
    return bool(SUPABASE_URL and SUPABASE_KEY)


def save_to_supabase(data: dict) -> None:
    """Сохраняет запись в Supabase через REST API."""
    if not supabase_enabled():
        return

    response = requests.post(
        f"{SUPABASE_URL}/rest/v1/{SUPABASE_TABLE}",
        headers={
            "apikey": SUPABASE_KEY,
            "Authorization": f"Bearer {SUPABASE_KEY}",
            "Content-Type": "application/json",
            "Prefer": "return=minimal",
        },
        json={
            "timestamp": data["timestamp"],
            "city": data["city"],
            "uv_index": data["uv_index"],
            "uv_desc": data["uv_desc"],
            "temperature": data["temperature"],
            "feels_like": data["feels_like"],
            "humidity": data["humidity"],
            "wind_speed": data["wind_speed"],
            "weather_desc": data["weather_desc"],
        },
        timeout=15,
    )
    response.raise_for_status()


def get_uv_from_supabase(city: str = None) -> dict:
    """Читает последнюю запись из Supabase."""
    if not supabase_enabled():
        return {}

    params = {
        "select": "id,timestamp,city,uv_index,uv_desc,temperature,feels_like,humidity,wind_speed,weather_desc",
        "order": "timestamp.desc",
        "limit": "1",
    }
    if city:
        params["city"] = f"eq.{city.strip().title()}"

    response = requests.get(
        f"{SUPABASE_URL}/rest/v1/{SUPABASE_TABLE}",
        headers={
            "apikey": SUPABASE_KEY,
            "Authorization": f"Bearer {SUPABASE_KEY}",
        },
        params=params,
        timeout=15,
    )
    response.raise_for_status()
    rows = response.json()
    return rows[0] if rows else {}


def save(data: dict):
    """Сохраняет запись в SQLite, а при наличии ENV — и в Supabase."""
    conn = init_db()
    conn.execute(
        "INSERT INTO uv_index "
        "(timestamp, city, uv_index, uv_desc, temperature, feels_like, humidity, wind_speed, weather_desc) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (data["timestamp"], data["city"], data["uv_index"], data["uv_desc"],
         data["temperature"], data["feels_like"], data["humidity"],
         data["wind_speed"], data["weather_desc"])
    )
    conn.commit()
    conn.close()

    # Supabase — опционально, без падения локального сценария.
    if supabase_enabled():
        try:
            save_to_supabase(data)
        except requests.RequestException as exc:
            print(f"⚠️  Supabase save failed: {exc}")


# ============================================================
# ЧТЕНИЕ ИЗ БД (для ваших макросов)
# ============================================================

def get_uv(city: str = None) -> dict:
    """Последняя запись. Supabase -> fallback SQLite."""
    if supabase_enabled():
        try:
            row = get_uv_from_supabase(city)
            if row:
                return row
        except requests.RequestException as exc:
            print(f"⚠️  Supabase read failed, fallback to SQLite: {exc}")

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    if city:
        row = conn.execute(
            "SELECT * FROM uv_index WHERE city = ? ORDER BY id DESC LIMIT 1",
            (city.strip().title(),)
        ).fetchone()
    else:
        row = conn.execute(
            "SELECT * FROM uv_index ORDER BY id DESC LIMIT 1"
        ).fetchone()
    conn.close()
    return dict(row) if row else {}


# ============================================================
# MAIN
# ============================================================

def main():
    city = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_CITY
    data = fetch_uv(city)
    save(data)

    print(f"""
☀️  UV Index — {data['city']}
{'─' * 35}
  UV Index:     {data['uv_index']} ({data['uv_desc']})
  Temperature:  {data['temperature']}°C (feels {data['feels_like']}°C)
  Humidity:     {data['humidity']}%
  Wind:         {data['wind_speed']} km/h
  Weather:      {data['weather_desc']}
  Time:         {data['timestamp']}
{'─' * 35}
✅ Saved to {DB_PATH}
""")


if __name__ == "__main__":
    main()
