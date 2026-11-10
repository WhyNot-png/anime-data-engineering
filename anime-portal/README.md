# Anime Portal — информационная система каталога аниме

Итоговый проект по дисциплине «Разработка на Python и инженерия данных»:
REST API на FastAPI для каталога аниме с пользовательскими списками просмотра,
отзывами и аналитикой, плюс простой клиентский интерфейс.

**Предметная область:** каталог аниме и личная библиотека просмотра. Пользователь
ведёт список тайтлов (планирую / смотрю / просмотрено / брошено), отмечает прогресс
по эпизодам, оставляет оценки и отзывы; система считает рейтинги, популярность
жанров и динамику выпуска по годам.

## Стек

Python 3.12 · FastAPI · Pydantic v2 · SQLAlchemy 2.0 (sync) · PostgreSQL 16 ·
Alembic · pytest + pytest-cov · ruff · mypy · Docker / docker compose · GitHub Actions.

## Быстрый старт

### Через Docker (рекомендуется)

```bash
cd anime-portal
docker compose up --build
```

Поднимаются PostgreSQL и API. При старте выполняется `alembic upgrade head` и
`python scripts/seed.py` (демо-данные). Открыть:

- интерфейс — http://localhost:8000/
- Swagger — http://localhost:8000/docs
- health — http://localhost:8000/health

### Локально

```bash
cd anime-portal
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"

cp .env.example .env                 # DATABASE_URL и прочие настройки
alembic upgrade head                 # схема только через миграции
python -m app.etl.import_anime --source data/anime.csv
python scripts/seed.py --skip-etl    # пользователи, списки, отзывы

uvicorn app.main:app --reload
```

Для быстрого локального запуска без PostgreSQL можно указать
`DATABASE_URL=sqlite:///./anime_portal.db` — схема та же, миграции совместимы.

## Переменные окружения

| Переменная | По умолчанию | Назначение |
| --- | --- | --- |
| `DATABASE_URL` | `sqlite:///./anime_portal.db` | строка подключения SQLAlchemy |
| `LOG_LEVEL` | `INFO` | уровень логирования |
| `PAGE_SIZE_DEFAULT` | `20` | размер страницы по умолчанию |
| `PAGE_SIZE_MAX` | `100` | максимум `size` (иначе 422) |

Секретов в коде нет; пример — `.env.example`, сам `.env` в `.gitignore`.

## Архитектура

```
anime-portal/
├── app/
│   ├── api/          # роутеры: anime, dictionaries, users, analytics, deps
│   ├── core/         # настройки, единый формат ошибок, логирование
│   ├── db/           # движок, сессия, Base, зависимость get_session
│   ├── models/       # SQLAlchemy-модели (7 таблиц)
│   ├── schemas/      # Pydantic: create / update / read + Page[T]
│   ├── services/     # бизнес-логика: catalog, watchlist, reviews, analytics
│   ├── etl/          # cleaning (чистые функции) и import_anime (CLI)
│   ├── static/       # клиент: index.html, app.js, style.css
│   └── main.py       # сборка приложения, /health, /docs
├── migrations/       # Alembic (одна обратимая миграция 0001)
├── tests/            # 72 теста: unit, интеграционные, миграции
├── docs/             # ERD, API, бизнес-правила, ETL, скриншоты
├── data/anime.csv    # демо-каталог для ETL
├── scripts/seed.py   # демо-данные
├── Dockerfile, docker-compose.yml, alembic.ini, pyproject.toml
```

Слои: `api → services → models`. Роутеры не содержат правил и SQL-логики,
сервисы не знают про HTTP (кроме доменных исключений с кодом ответа).

## Сущности и ERD

6 сущностей + ассоциативная таблица: `studios`, `anime`, `genres`, `anime_genres`,
`users`, `watch_entries`, `reviews`. Связи один-ко-многим и многие-ко-многим,
`UNIQUE`/`CHECK`/`FK`, индексы по полям поиска и фильтрации.

Полная ERD-диаграмма (Mermaid), список ограничений и индексов — [docs/erd.md](docs/erd.md).

## Бизнес-правила

1. **BR-1.** Один тайтл — одна запись в списке просмотра (`409` при повторе).
2. **BR-2.** Прогресс не больше числа эпизодов; достижение конца автоматически
   переводит запись в `completed`; `completed` без полного просмотра запрещён.
3. **BR-3.** Отзыв доступен только после `completed`, один отзыв на тайтл.
4. **BR-4.** Тайтл с отзывами удалить нельзя (и студию с тайтлами).
5. **BR-5.** Рейтинги и топ-N считаются агрегацией по отзывам, а не хранимым полем.

Детали и привязка к тестам — [docs/business-rules.md](docs/business-rules.md).

## ETL

`python -m app.etl.import_anime --source data/anime.csv --report logs/etl-report.json`

Извлечение → валидация и очистка (пропуски, дубликаты, форматы, алиасы статусов,
жанры) → загрузка в одной транзакции. Идемпотентно: повторный запуск обновляет
записи по `mal_id` и не создаёт дубликатов. В лог и JSON-отчёт попадают числа
принятых/отклонённых строк и причины отказа. Подробно — [docs/etl.md](docs/etl.md).

## API

14 эндпоинтов: CRUD каталога, справочники, пользователи, списки просмотра,
отзывы и 3 аналитических отчёта. Пагинация, фильтрация и сортировка — в
`GET /api/v1/anime`. Единый формат ошибок, раздельные схемы create/update/read,
`Depends` для сессии БД, автодокументация с примерами.

Полная таблица и `curl`-примеры — [docs/api.md](docs/api.md). Swagger доступен на
`/docs` и содержит описания, коды ошибок и примеры запросов для каждого эндпоинта.

## Клиентский интерфейс

Одностраничный клиент на HTML/JS (`app/static`), работает через тот же API:
каталог с поиском, фильтрами и пагинацией; создание и редактирование тайтла;
список просмотра с бизнес-операцией «+1 эпизод» (автозавершение); форма отзыва;
аналитика; ошибки API показываются пользователю.

Экраны клиента:

- **Каталог** — таблица тайтлов (название, год, эпизоды, студия, жанры, средняя оценка),
  поиск по названию, фильтры по жанру, статусу и годам, сортировка, пагинация,
  кнопки «В список», «Отзыв», «Изменить», «Удалить».
- **Мой список** — карточки записей со статусом и прогрессом (`просмотрено / всего`),
  кнопка «+1 эп.» (вызывает бизнес-операцию и автозавершает тайтл), «Бросить», «Убрать»,
  фильтр по статусу.
- **Аналитика** — три таблицы: топ по средней оценке, популярность жанров,
  динамика по годам.
- **Ошибки** — ответ API в едином формате выводится в верхней панели вместе с кодом,
  например «Сначала добавьте тайтл в список просмотра. (conflict)».

## Тесты и качество

```bash
pytest                                  # 72 теста, покрытие 96%+
pytest --cov=app --cov-report=html      # HTML-отчёт в htmlcov/
ruff check . && ruff format --check .
mypy app
```

- unit-тесты сервисов и очистки ETL (`tests/test_services.py`, `tests/test_etl_cleaning.py`);
- интеграционные тесты API через `TestClient`, включая негативные сценарии
  (`tests/test_api_*.py`);
- тест обратимости миграций и отсутствия дрейфа схемы (`tests/test_migrations.py`);
- отдельная тестовая БД на каждый тест (файл SQLite в `tmp_path`), в CI — PostgreSQL.

## CI

`.github/workflows/anime-portal-ci.yml`: ruff (lint + format), миграции
upgrade/downgrade на PostgreSQL, два прогона ETL (идемпотентность), `pytest`
с порогом покрытия 70%, smoke-проверка живого сервера и отдельная job со
сборкой Docker-образа и `docker compose up`.

## Структура отчётности

- ERD и ограничения — [docs/erd.md](docs/erd.md)
- Бизнес-правила — [docs/business-rules.md](docs/business-rules.md)
- ETL — [docs/etl.md](docs/etl.md)
- API — [docs/api.md](docs/api.md)
