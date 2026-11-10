# ERD — Anime Portal

Схема БД: 6 сущностей и ассоциативная таблица. Связи: один-ко-многим (`studios → anime`,
`users → watch_entries`, `anime → reviews`) и многие-ко-многим (`anime ↔ genres` через
`anime_genres`).

```mermaid
erDiagram
    STUDIOS ||--o{ ANIME : "produces"
    ANIME ||--o{ ANIME_GENRES : "has"
    GENRES ||--o{ ANIME_GENRES : "labels"
    USERS ||--o{ WATCH_ENTRIES : "keeps"
    ANIME ||--o{ WATCH_ENTRIES : "listed_in"
    USERS ||--o{ REVIEWS : "writes"
    ANIME ||--o{ REVIEWS : "receives"

    STUDIOS {
        int id PK
        string name UK "NOT NULL, UNIQUE, индекс"
        string country
        int founded_year "CHECK 1900..2100"
    }
    ANIME {
        int id PK
        int mal_id UK "UNIQUE, индекс"
        string title "NOT NULL, индекс, CHECK length 1..300"
        string title_english
        text synopsis
        int year "CHECK 1900..2100, индекс"
        int episodes "CHECK >= 0"
        string status "CHECK: upcoming|airing|finished, индекс"
        int studio_id FK "-> studios.id ON DELETE RESTRICT, индекс"
        datetime created_at
        datetime updated_at
    }
    GENRES {
        int id PK
        string name UK "UNIQUE, индекс"
        string slug UK "UNIQUE"
    }
    ANIME_GENRES {
        int anime_id PK, FK "-> anime.id ON DELETE CASCADE"
        int genre_id PK, FK "-> genres.id ON DELETE CASCADE, индекс"
    }
    USERS {
        int id PK
        string email UK "UNIQUE, индекс"
        string username UK "UNIQUE"
        datetime created_at
    }
    WATCH_ENTRIES {
        int id PK
        int user_id FK "-> users.id ON DELETE CASCADE, индекс"
        int anime_id FK "-> anime.id ON DELETE CASCADE, индекс"
        string status "CHECK: planned|watching|completed|dropped"
        int progress "CHECK >= 0"
        datetime created_at
        datetime updated_at
    }
    REVIEWS {
        int id PK
        int user_id FK "-> users.id ON DELETE CASCADE, индекс"
        int anime_id FK "-> anime.id ON DELETE CASCADE, индекс"
        int rating "CHECK 1..10"
        text body "CHECK length <= 2000"
        datetime created_at
    }
```

## Ограничения целостности

| Ограничение | Где | Смысл |
| --- | --- | --- |
| `UNIQUE(users.email)`, `UNIQUE(users.username)` | `users` | один аккаунт на email/имя |
| `UNIQUE(anime.mal_id)` | `anime` | идемпотентность ETL по внешнему id |
| `UNIQUE(watch_entries.user_id, anime_id)` | `watch_entries` | один тайтл — одна запись в списке |
| `UNIQUE(reviews.user_id, anime_id)` | `reviews` | один отзыв на тайтл от пользователя |
| `CHECK status IN (...)` | `anime`, `watch_entries` | допустимые состояния |
| `CHECK rating BETWEEN 1 AND 10` | `reviews` | шкала оценок |
| `CHECK progress >= 0`, `CHECK episodes >= 0` | `watch_entries`, `anime` | неотрицательные счётчики |
| `CHECK year BETWEEN 1900 AND 2100` | `anime`, `studios` | правдоподобные годы |
| `FK ... ON DELETE CASCADE` | `anime_genres`, `watch_entries`, `reviews` | удаление тайтла/пользователя чистит зависимые строки |
| `FK studio_id ... ON DELETE RESTRICT` | `anime` | студию с тайтлами удалить нельзя |

## Индексы

Поиск и фильтрация: `anime.title`, `anime.year`, `anime.status`, `anime.studio_id`,
`anime.mal_id`, `genres.name`, `studios.name`, `users.email`,
`watch_entries.user_id`, `watch_entries.anime_id`, `reviews.anime_id`, `reviews.user_id`,
`anime_genres.genre_id`.

Схема создаётся и меняется только миграциями Alembic: `alembic upgrade head`,
откат — `alembic downgrade base` (проверяется тестом `tests/test_migrations.py`).
