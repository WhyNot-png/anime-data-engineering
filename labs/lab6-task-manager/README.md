# Задание 6. Менеджер задач — FastAPI + PostgreSQL

Учебный REST API по практической работе: пользователи и их задачи, асинхронная
SQLAlchemy 2.0, Pydantic v2, миграции Alembic и middleware Starlette.
Прошлые задания проекта не изменяются: сервис находится в отдельном каталоге.

## Требования

- Git, Docker Engine/Desktop и Docker Compose v2.
- Для запуска вне контейнера и тестов: Python 3.12.12 и uv 0.13.5
  (либо pip + виртуальное окружение).
- Порты localhost 5432 и 8000 должны быть свободны.

> Учебный сервис без аутентификации, как в условии. Публикация портов ограничена
> `127.0.0.1`. Пароль `app` в примере — открытое учебное значение, не настоящий
> секрет. Не используйте этот пароль и такую модель доступа в production.

## Быстрый запуск — всё в Docker

Команды для Bash / Linux / macOS; на Windows используйте терминал Git Bash.

```bash
git clone https://github.com/WhyNot-png/anime-data-engineering.git
cd anime-data-engineering/labs/lab6-task-manager
cp .env.example .env
docker compose up -d db
docker compose exec db psql -U app -d tasks -c "select 1"
docker compose up -d --build app
docker compose logs app
```

Контейнер API сам выполняет **`alembic upgrade head`**, затем запускает Uvicorn.
`depends_on` ждёт healthcheck PostgreSQL. Таблицы через `create_all` не создаются.
Откройте http://localhost:8000/docs — Swagger UI; спецификация — `/openapi.json`.

```bash
# Таблицы и версия миграции
docker compose exec db psql -U app -d tasks -c '\dt'
docker compose exec app alembic current

# Остановить, сохранив данные
docker compose down
```

**Удаление данных (не требуется для обычной остановки):** `docker compose down -v`.

## Альтернатива: API локально, PostgreSQL в Docker

```bash
# Выполнять из labs/lab6-task-manager после cp .env.example .env
docker compose up -d db
uv sync --locked
uv run alembic upgrade head
uv run uvicorn app.main:app --reload --log-config logging.json
```

В `.env` используется `DATABASE_URL=postgresql+asyncpg://app:app@localhost:5432/tasks`.
В контейнере Compose подставляет хост `db` вместо `localhost`. Настройки читаются
через `pydantic-settings`; в `app/` и `alembic.ini` строки подключения нет.
URL хранится в `SecretStr`, не печатается в логах; `.env` исключён из Git.

Вариант без uv:

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
alembic upgrade head
uvicorn app.main:app --reload --log-config logging.json
```

На PowerShell активация: `.venv\Scripts\Activate.ps1`, копирование: `Copy-Item .env.example .env`.
`requirements.txt` содержит точные runtime-версии; `requirements-dev.txt` — также тестовые.
Полный граф зависимостей сохранён в `uv.lock`, версия Python — в `.python-version`.

## API и ручная проверка через Swagger

| Метод | Путь | Назначение | Основные коды |
| --- | --- | --- | --- |
| POST | `/users` | Создать пользователя | 201, 409, 422 |
| GET | `/users/{id}` | Получить пользователя | 200, 404 |
| POST | `/tasks` | Создать задачу | 201, 404, 422 |
| GET | `/tasks` | Фильтры и пагинация | 200, 422 |
| GET | `/tasks/{id}` | Получить задачу | 200, 404 |
| PATCH | `/tasks/{id}` | Частичное обновление | 200, 404, 422 |
| DELETE | `/tasks/{id}` | Удалить, пустое тело | 204, 404 |

1. `/docs` → `POST /users` → **Try it out** → тело
   `{"email":"student@example.com","name":"Student"}` → **Execute**, ожидается 201.
2. Скопируйте полученный `id`; повторный POST с тем же email вернёт 409.
3. `POST /tasks`: `{"title":"Подготовить отчёт","owner_id":1}`. Вместо 1 укажите
   фактический id пользователя; ожидается 201. Несуществующий владелец → 404.
4. `GET /tasks`, фильтры `done=false`, `owner_id=<id>`, `limit=20`, `offset=0`.
5. `GET /tasks/{id}` → 200; `PATCH /tasks/{id}` с `{"done":true}` → 200.
6. `DELETE /tasks/{id}` → 204; повторный GET этого id → 404.
7. Пустой title, title длиннее 200 символов, `limit=101` → 422.

Список упорядочен по `id`, `limit` ограничен 1–100, `offset >= 0`.
PATCH использует `model_dump(exclude_unset=True)`: пропущенные поля не меняются;
`{"description":null}` очищает описание. Явный null для title/done/owner_id → 422.
Создание и чтение используют отдельные схемы; `UserUpdate` тоже определена, но
неиспрошенный эндпоинт обновления пользователя не добавляется.

## Скриншоты реального выполнения

Снимки сделаны в настоящем Swagger UI, запросы отправлены через кнопки Execute.
Исходные PNG без перерисовки упакованы в SVG для текстового API GitHub.
[Машинный протокол HTTP-запросов](evidence/swagger-requests.json).

### Создание пользователя — 201

![Swagger POST users 201](screenshots/swagger-user-201.svg)

### Создание задачи — 201

![Swagger POST tasks 201](screenshots/swagger-task-201.svg)

### Получение задачи — 200

![Swagger GET task 200](screenshots/swagger-task-200.svg)

### Удалённая задача — 404

![Swagger GET deleted task 404](screenshots/swagger-task-404.svg)

### Таблицы PostgreSQL: настоящая консоль psql и команда \dt

![PostgreSQL psql tables](screenshots/postgresql-tables.svg)

На снимке видны `users`, `tasks`, `alembic_version`. Это реальная psql-сессия,
открытая через локальный ttyd; таблицы созданы применением Alembic.
Локальная проверка использовала PostgreSQL 16, запущенный нативно на порту 55432,
и локальный Uvicorn. Это не выдаётся за локальный запуск Docker: в агентском
окружении Docker отсутствовал. **Docker-сценарий успешно выполнен в GitHub Actions**:
[запуск 40242948467](https://github.com/WhyNot-png/anime-data-engineering/actions/runs/40242948467).
Подтверждены сборка образа, запуск Compose, HTTP CRUD, тесты на PostgreSQL и отсутствие
расхождений миграции. [Протокол статусов шагов CI](evidence/docker-ci.json).

## Миграции

Первоначально выполнено `alembic init -t async migrations`, затем на пустой БД:

```bash
uv run alembic revision --autogenerate -m "create users and tasks"
uv run alembic upgrade head
uv run alembic check
```

Первая миграция `8cc1a0909584` уже закоммичена: при клонировании **не генерируйте её
повторно**, достаточно `upgrade head`. В ней созданы уникальный email, внешний
ключ owner_id, индекс владельца, ограничение длины title и серверные значения
по умолчанию. `Mapped`/`mapped_column`, `relationship(back_populates=...)` задают
связь один-ко-многим. Сессия — `AsyncSession`, зависимость через `yield`.

Для разработки новых изменений: поправить модели → `revision --autogenerate` →
вручную проверить миграцию → `upgrade head`. На пустой отдельной тестовой базе
проверены downgrade до base и повторный upgrade; не запускайте откат на рабочей
базе без резервной копии — эта миграция удаляет таблицы при downgrade.

## Автотесты

Тесты запускаются только с **отдельной** базой с именем, заканчивающимся на `_test`.
Они используют настоящий PostgreSQL, не SQLite. Внешняя транзакция и SAVEPOINT
откатывают изменения каждого теста, несмотря на `session.commit()` внутри роутеров.

```bash
docker compose up -d db
uv sync --locked
docker compose exec db psql -U app -d tasks -c "CREATE DATABASE tasks_test OWNER app;"
DATABASE_URL=postgresql+asyncpg://app:app@localhost:5432/tasks_test uv run alembic upgrade head
TEST_DATABASE_URL=postgresql+asyncpg://app:app@localhost:5432/tasks_test uv run pytest
uv run ruff check .
uv run ruff format --check .
```

`CREATE DATABASE` выполняется один раз. В PowerShell переменные задаются через
`$env:TEST_DATABASE_URL="..."`; после команды верните DATABASE_URL основной базы,
если изменяли её в текущем сеансе.

Проверяются CRUD, уникальность email и rollback после 409, отсутствие владельца,
ошибки 404/422, границы длины title, оба значения done, owner_id, пагинация,
частичный PATCH и явный null, пустой 204, middleware и OpenAPI.
Локально: **32 теста пройдены**, суммарное покрытие строк и ветвей — **83,86%**.
Порог покрытия приложения — 80%; [реальный лог](evidence/pytest.txt).

С работающим API можно повторить проверку настоящих HTTP-запросов:

```bash
uv run python scripts/smoke_api.py
```

Скрипт оставляет созданного учебного пользователя, задачу удаляет. Не запускайте
его на чужом или production-сервисе.

## CI

[Workflow lab6-api.yml](../../.github/workflows/lab6-api.yml) на GitHub Actions:
проверка lock/lint/форматирования → `docker compose up --build` → реальный HTTP
smoke → миграция отдельной тестовой БД → pytest → `alembic check`. Логи контейнеров
выводятся перед очисткой даже при ошибке. Секреты и доступ к личным аккаунтам не нужны.

## Middleware

В каждый обработанный ответ добавляется `X-Process-Time` (секунды, монотонный
`perf_counter`). Лог содержит метод, путь без query string, HTTP-статус и время.
Тело запроса и DATABASE_URL не логируются. Конфигурация `logging.json` включает
INFO для именованного логгера, вывод — в stderr.

## Ответы на контрольные вопросы

1. **FastAPI и Starlette.** Starlette — ASGI-инструментарий для HTTP/WebSocket,
   маршрутизации, middleware, Request/Response, исключений и жизненного цикла.
   FastAPI построен поверх него и добавляет извлечение/валидацию параметров через
   Pydantic, зависимости `Depends`, сериализацию по схемам, OpenAPI и Swagger UI.
   В работе используются middleware, Request/Response и lifespan Starlette.
2. **Зачем Create, Read и Update?** Create описывает вход создания, без генерируемых
   id/created_at; Read — ответ с этими полями. Update допускает пропуск полей для
   PATCH. Разделение не позволяет клиенту задавать служебные значения и устраняет
   путаницу обязательности; разрешённость пропуска не тождественна разрешению null.
3. **`from_attributes=True`.** Pydantic читает значения из атрибутов объекта ORM,
   а не только из словаря: `UserRead.model_validate(user)`. Нужные поля должны быть
   загружены; настройка сама не выполняет асинхронную ленивую загрузку отношений.
4. **Почему Depends, а не глобальная сессия?** AsyncSession — изменяемая транзакционная
   единица, её нельзя разделять между параллельными запросами. Зависимость создаёт
   сессию на запрос, закрывает её через async context manager и позволяет подмену
   в тестах. Общий engine/пул и фабрика сессий допустимы, общая сессия — нет.
5. **`exclude_unset` и `exclude_none`.** Первый исключает поля, которых не было во
   входе, но сохраняет явно присланный null. Второй исключает все значения None,
   даже явно переданные. Для PATCH это принципиально: `description=null` должно
   очистить столбец, а пропущенное description — оставить его без изменений.
6. **Почему не `create_all` в production?** Он создаёт отсутствующие таблицы, но не
   описывает историю и управляемую эволюцию существующей схемы/данных. Alembic даёт
   версионированные, проверяемые шаги upgrade/downgrade; сложные изменения и откаты
   всё равно требуют ручной проверки, резервных копий и плана развёртывания.

## Структура

```text
app/                    # main, config, db, models, schemas, routers
migrations/             # async env.py и первая автогенерированная миграция
scripts/smoke_api.py     # проверка реального HTTP CRUD
tests/                  # интеграционные тесты на отдельной PostgreSQL БД
screenshots/            # подлинные браузерные снимки
evidence/               # протокол запросов и лог тестов
Dockerfile
docker-compose.yml
.env.example
requirements.txt        # точные runtime-зависимости
requirements-dev.txt
pyproject.toml
uv.lock
README.md
```

## Продолжение: задание 7

[Тестирование, многоэтапный Docker и CI/CD с публикацией образов](../lab7-api-ci/README.md).
