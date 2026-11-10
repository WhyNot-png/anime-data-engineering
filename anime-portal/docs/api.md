# API: эндпоинты и примеры

База: `http://localhost:8000/api/v1`. Swagger: `/docs`, OpenAPI: `/openapi.json`.

## Каталог

| Метод | Путь | Назначение | Коды |
| --- | --- | --- | --- |
| GET | `/anime` | список: `q`, `genre`, `studio_id`, `year_from`, `year_to`, `status`, `sort`, `page`, `size` | 200, 422 |
| POST | `/anime` | создать тайтл | 201, 409, 422 |
| GET | `/anime/{id}` | карточка тайтла | 200, 404 |
| PATCH | `/anime/{id}` | частичное обновление | 200, 404, 409, 422 |
| DELETE | `/anime/{id}` | удалить (нельзя при наличии отзывов) | 204, 404, 409 |

## Справочники

| Метод | Путь | Назначение | Коды |
| --- | --- | --- | --- |
| GET | `/studios` | студии с пагинацией | 200 |
| POST | `/studios` | создать студию | 201, 409 |
| DELETE | `/studios/{id}` | удалить студию без тайтлов | 204, 404, 409 |
| GET | `/genres` | все жанры | 200 |
| POST | `/genres` | создать жанр (slug из имени) | 201, 409 |

## Пользователи, списки, отзывы

| Метод | Путь | Назначение | Коды |
| --- | --- | --- | --- |
| GET | `/users` | список пользователей | 200 |
| POST | `/users` | создать пользователя | 201, 409, 422 |
| GET | `/users/{id}` | пользователь | 200, 404 |
| GET | `/users/{id}/watchlist` | список просмотра, фильтр `status` | 200, 404 |
| POST | `/users/{id}/watchlist` | добавить тайтл (BR-1) | 201, 404, 409 |
| PATCH | `/watchlist/{id}` | прогресс/статус (BR-2) | 200, 404, 409, 422 |
| DELETE | `/watchlist/{id}` | убрать из списка | 204, 404 |
| GET | `/anime/{id}/reviews` | отзывы тайтла | 200, 404 |
| POST | `/anime/{id}/reviews?user_id=` | отзыв (BR-3) | 201, 404, 409, 422 |
| DELETE | `/reviews/{id}` | удалить отзыв | 204, 404 |

## Аналитика

| Метод | Путь | Назначение |
| --- | --- | --- |
| GET | `/analytics/top-anime?limit=&min_reviews=` | топ по средней оценке |
| GET | `/analytics/genres?limit=` | тайтлы и средняя оценка по жанрам |
| GET | `/analytics/years?year_from=&year_to=` | динамика по годам |

Служебное: `GET /health` (вне `/api/v1`).

## Формат ошибок

```json
{
  "error": {
    "code": "conflict",
    "message": "Нельзя завершить «Death Note»: просмотрено 30 из 37 эпизодов.",
    "details": null
  }
}
```

Коды: `not_found` (404), `conflict` (409), `validation_error` (422),
`http_error`/`method_not_allowed` (4xx), `bad_request` (400).

## Примеры

```bash
# список с фильтрами и сортировкой
curl "http://localhost:8000/api/v1/anime?genre=sci-fi&sort=-year&page=1&size=5"

# создание тайтла
curl -X POST http://localhost:8000/api/v1/anime \
  -H 'Content-Type: application/json' \
  -d '{"title":"Steins;Gate","year":2011,"episodes":24,"status":"finished","genre_ids":[1]}'

# бизнес-операция: отметить просмотр последнего эпизода
curl -X PATCH http://localhost:8000/api/v1/watchlist/1 \
  -H 'Content-Type: application/json' -d '{"progress":37}'
# -> 200 {"status":"completed", ...}

# негативный сценарий: прогресс больше числа эпизодов
curl -X PATCH http://localhost:8000/api/v1/watchlist/1 \
  -H 'Content-Type: application/json' -d '{"progress":999}'
# -> 409 {"error":{"code":"conflict", ...}}

# отзыв до завершения просмотра
curl -X POST "http://localhost:8000/api/v1/anime/1/reviews?user_id=1" \
  -H 'Content-Type: application/json' -d '{"rating":9}'
# -> 409 {"error":{"code":"conflict","message":"Сначала добавьте тайтл в список просмотра."}}

# аналитика
curl "http://localhost:8000/api/v1/analytics/top-anime?limit=3&min_reviews=1"
```
