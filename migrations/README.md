# Database Migrations

Все миграции нужно выполнять в Supabase SQL Editor в правильном порядке.

## Порядок выполнения миграций

### 1. ✅ add_countries.sql
**Статус:** Должна быть уже выполнена

Добавляет поддержку стран:
- Создает таблицу `countries`
- Добавляет `country_id` к таблице `cities`
- Обновляет RPC функцию `get_uv_for_banner`

### 2. 🆕 add_universal_api.sql
**Статус:** НОВАЯ — нужно выполнить

Добавляет универсальные API endpoints:
- `get_weather_data(p_city, p_fields)` — один город, любые параметры
- `get_weather_data_batch(p_cities[], p_fields)` — несколько городов
- `get_weather_data_by_country(p_country_code, p_fields)` — все города страны

**Как выполнить:**
1. Открыть Supabase Dashboard → SQL Editor
2. Скопировать весь код из `add_universal_api.sql`
3. Вставить и нажать "Run"

### 3. ⚙️ add_batch_support.sql (опционально)
**Статус:** Опциональная — только для масштабирования 500+ городов

Добавляет колонку `batch` для разделения городов на группы.

**Когда использовать:**
- Если планируете обкачивать 500+ городов
- Если хотите разделить обработку на несколько запусков

## Новые API endpoints

После выполнения миграции `add_universal_api.sql` будут доступны:

### 1. Single City (универсальная замена get_uv_for_banner)
```javascript
fetch('YOUR_URL/rest/v1/rpc/get_weather_data', {
  method: 'POST',
  headers: { 'apikey': 'YOUR_KEY', 'Content-Type': 'application/json' },
  body: JSON.stringify({
    p_city: 'Mumbai',
    p_fields: ['uv_index', 'temperature', 'humidity']  // любые параметры!
  })
})
```

### 2. Multiple Cities
```javascript
fetch('YOUR_URL/rest/v1/rpc/get_weather_data_batch', {
  method: 'POST',
  headers: { 'apikey': 'YOUR_KEY', 'Content-Type': 'application/json' },
  body: JSON.stringify({
    p_cities: ['Mumbai', 'Delhi', 'Bangalore'],
    p_fields: ['temperature']  // только температура для всех городов
  })
})
```

### 3. All Cities from Country
```javascript
fetch('YOUR_URL/rest/v1/rpc/get_weather_data_by_country', {
  method: 'POST',
  headers: { 'apikey': 'YOUR_KEY', 'Content-Type': 'application/json' },
  body: JSON.stringify({
    p_country_code: 'IN',
    p_fields: ['uv_index', 'weather_desc']
  })
})
```

## Доступные параметры (p_fields)

Можно запрашивать любую комбинацию:
- `uv_index` — UV индекс
- `uv_desc` — описание UV (Low, Moderate, High, Very High, Extreme)
- `temperature` — температура °C
- `feels_like` — ощущается как °C
- `humidity` — влажность %
- `wind_speed` — скорость ветра км/ч
- `weather_desc` — описание погоды (Clear sky, Rain, etc.)
- `updated_at` — время обновления

**Если `p_fields` не указан или `null` — возвращаются все поля.**

## Примеры использования

### Баннер только с UV
```javascript
p_fields: ['uv_index', 'uv_desc']
// Ответ: { ok: true, city: "Mumbai", uv_index: 7.5, uv_desc: "High" }
```

### Баннер с температурой и влажностью
```javascript
p_fields: ['temperature', 'humidity', 'weather_desc']
// Ответ: { ok: true, city: "Delhi", temperature: 35.2, humidity: 45, weather_desc: "Clear sky" }
```

### Полная информация
```javascript
p_fields: null  // или не указывать
// Ответ: { ok: true, city: "Mumbai", uv_index: 7.5, temperature: 32.1, ... все поля }
```
