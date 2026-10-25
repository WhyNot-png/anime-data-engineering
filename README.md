# Anime Data Engineering

## Задание 6: REST API «Менеджер задач»

[Код и полный README-отчёт](labs/lab6-task-manager/README.md): FastAPI, PostgreSQL 16,
асинхронная SQLAlchemy 2.0, Pydantic v2 и Alembic. В отчёте — команды запуска,
подлинные скриншоты Swagger 201/200/404, `\dt` в psql и ответы на все шесть вопросов.
Сервис изолирован в `labs/lab6-task-manager`, прошлые задания не заменяет.

## Задание 3: T1 + P3

Сайт на MkDocs Material: сравнительный анализ четырёх Python SSG и воспроизводимый
конвейер числовых данных MyAnimeList → агрегаты/график → статические страницы.
Планируемый адрес после первого deploy: https://whynot-png.github.io/anime-data-engineering/

```bash
uv sync --locked --group docs
uv run --group docs nox -s site
uv run --group docs mkdocs serve
```

Отчёты: `docs/t1.md`, `docs/p3.md`, `docs/report.md`. Числовые входы и источник —
`research/`; результаты генерируются в `docs/generated/` и не коммитятся.
Перезапуск замеров: `uv run --group docs python scripts/benchmark_experiment.py` и
`uv run --group docs --group benchmark python scripts/benchmark_ssg.py`.
Для воспроизводимости небольшого ETL-эксперимента в Git хранится атрибутированный
числовой CSV около 550 КиБ; для этого файла явно разрешён размер в pre-commit.

Публикация: Settings → Pages → Source = GitHub Actions, затем merge PR в main.
Workflow `.github/workflows/pages.yml` собирает каждую ветку, публикует только main
и проверяет HTTP/контрольную строку. Отечественный хостинг **исключён по просьбе
автора** и не заявляется выполненным. В отчёте явно отмечены непроверенные части
развёртывания и браузерной проверки графика. Тег lab1 не изменяется.

---


![CI](https://github.com/WhyNot-png/anime-data-engineering/actions/workflows/ci.yml/badge.svg?branch=main)

Учебный проект по инженерии данных об аниме: воспроизводимая обработка выбранного
снимка MyAnimeList, очистка CSV и подготовка данных для исследований. Лабораторная 1
создаёт устанавливаемый Python-пакет, безопасную конфигурацию, CLI и контроль качества.
Существовавший ETL сохранён как необязательное расширение; запуск каркаса не требует
доступа к Kaggle, GitHub-токена или скачивания данных.

## Источник данных

[MyAnimeList Anime Database — July 2025 (Kaggle)](https://www.kaggle.com/datasets/sazzadsiddiquelikhon/myanimelist-anime-database-july-2025)
— публичный табличный снимок MyAnimeList об аниме, выбранный в исходном проекте.
По метаданным Kaggle: **более 28 000 тайтлов**, обновление 16 июля 2025 года,
объём файлов около 9,5 МБ. Задача проекта — нормализация колонок, удаление
дубликатов и загрузка очищенных данных в SQLite для дальнейших исследований.
Фактическая схема CSV и точное количество строк фиксируются после загрузки,
а не выводятся из рекламного описания набора.

Существование и публичность набора проверены через
[API каталога Kaggle](https://www.kaggle.com/api/v1/datasets/list?search=myanimelist-anime-database-july-2025).
Карточка указывает лицензию «Database: Open Database, Contents: © Original Authors»:
права на базу и оригинальный контент различаются. Перед распространением исходных
данных нужно прочитать условия в карточке; данные не включены в Git.
Реальная загрузка требует настроенного Kaggle API и отдельно не выполняется в ЛР1.

## Требования

- Git; [uv **0.13.5**](https://docs.astral.sh/uv/getting-started/installation/).
- Python **3.12.12** по умолчанию (`.python-version`); поддерживается также 3.13.9.
  `uv` автоматически установит выбранный Python, если он отсутствует.
- Команда `rg` этого проекта не связана с ripgrep: используйте именно `uv run rg`.

## Установка: две команды после клонирования

```bash
git clone https://github.com/WhyNot-png/anime-data-engineering.git
cd anime-data-engineering
```

Затем ровно две команды для установки и работающего проекта:

```bash
uv sync --locked
uv run rg check-config
```

Первый вызов устанавливает пакет и dev-инструменты из `uv.lock`. Dev-группа также
содержит pandas, pyarrow и SQLAlchemy для тестирования ранее существовавшего ETL.
В runtime-зависимостях каркаса только pydantic, pydantic-settings и typer.
Для минимального окружения без инструментов разработки: `uv sync --locked --no-dev`.

## Конфигурация

Настройки читаются из `.env` и переменных окружения; окружение имеет приоритет.
Копирование `.env.example` в `.env` необязательно: безопасные значения уже заданы.
`.env` и токены нельзя добавлять в Git. Файл `.env.example` содержит все ключи.

| Переменная | По умолчанию | Назначение |
| --- | --- | --- |
| `RG_GITHUB_TOKEN` | не задан | Необязательный токен для будущих ЛР; сейчас не требуется |
| `RG_DATA_DIR` | `data` | Корневой каталог данных; относительный путь от текущего каталога |
| `RG_LOG_LEVEL` | `INFO` | DEBUG, INFO, WARNING, ERROR, CRITICAL; регистр нормализуется |
| `RG_LOG_FORMAT` | `text` | `text` или построчный JSON (`json`) |
| `RG_REQUEST_TIMEOUT` | `30.0` | Таймаут в секундах, 0 < значение ≤ 300; NaN/inf запрещены |
| `RG_MAX_CONCURRENCY` | `8` | Число параллельных операций, от 1 до 64 |

`get_settings()` не кэшируется. `Settings.ensure_data_dir()` создаёт каталог
идемпотентно; `check-config` только проверяет настройки и не создаёт данные.
Не передавайте секреты как аргументы CLI. Сводка выводит лишь булев признак токена,
а ошибки валидации не печатают исходные значения.

## Использование

```bash
uv run rg --help
uv run rg version
uv run rg check-config
```

`version` выводит `0.1.0`. Пример stdout для `check-config`:

```json
{
  "data_dir": "data",
  "log_level": "INFO",
  "log_format": "text",
  "request_timeout": 30.0,
  "max_concurrency": 8,
  "github_token_configured": false
}
```

В stderr отдельно выводится запись с временем, уровнем, именем логгера и сообщением.
Для JSON-логов задайте `RG_LOG_FORMAT=json` в `.env` или окружении.
При ошибке конфигурации команда возвращает код 2, при успехе — 0.

## Разработка

```bash
uv run ruff check .
uv run ruff format --check .
uv run mypy
uv run pytest
uv run pre-commit install
uv run pre-commit run --all-files
```

`mypy` работает в strict-режиме на всём `src` и `tests`; нет глобального подавления
ошибок импорта. Точечные overrides относятся к необязательным Kaggle/SQLAlchemy,
а для pandas установлены заглушки. Порог branch coverage — **70%**, зафиксирован
в `pyproject.toml`. Тесты изолируют `RG_*`, `.env`, рабочую директорию и логирование.
Интеграционные тесты создают маленькие CSV локально и проверяют CSV → Parquet → SQLite;
внешние запросы и реальные секреты не нужны.

Хуки ruff/mypy запускаются через `uv run --locked`, поэтому версии совпадают с CI.
Первый pre-commit может исправить форматирование: проверьте diff и повторите запуск.
Проверки самого Git-репозитория: `uv run python scripts/check_repository.py`.

CI запускается на push в `main` и рабочую ветку `lab1-compliance`, pull request,
тег `lab1` и вручную. Матрица — Python **3.12.12 / 3.13.9** × **Ubuntu / Windows**.
Каждая job проверяет lint, форматирование, типы, тесты/покрытие, CLI, гигиену Git,
pre-commit и сборку wheel/sdist. Секреты не требуются, права workflow — `contents: read`.
Workflow фиксирует сторонние actions по SHA, uv — по версии и кэширует зависимости.
Историю запусков смотрите во вкладке [Actions](https://github.com/WhyNot-png/anime-data-engineering/actions).

## Структура проекта

```text
.python-version                  # основной Python
pyproject.toml                   # пакет, зависимости и правила проверок
uv.lock                          # зафиксированный граф зависимостей
.env.example                     # безопасный пример настроек
src/
  research_graph/                # устанавливаемый пакет (src-layout)
    __init__.py                  # версия пакета
    config.py                    # Settings / get_settings
    logging_setup.py             # stderr, text/JSON
    cli.py                       # rg version / check-config
    models/                      # заготовка моделей
    sources/                     # заготовка источников
    storage/                     # заготовка хранилищ
    pipelines/                   # сохранённый необязательный ETL
    api/                         # заготовка API
  extract.py, transform.py,       # обёртки старых импортов
  load.py, main.py
scripts/check_repository.py      # запрет служебных артефактов в Git
tests/                           # конфигурация, CLI, логи, ETL
.github/workflows/ci.yml          # матрица проверок
.pre-commit-config.yaml          # локальные хуки
docs/lab1_report.md               # короткий отчёт
```

## Сохранённый ETL и Jupyter (не нужны для ЛР1)

```bash
uv sync --locked --extra etl
uv run python -m research_graph.pipelines.main
```

Для реальной загрузки отдельно настройте Kaggle API в `~/.kaggle/kaggle.json`
по документации Kaggle. `RG_GITHUB_TOKEN` не является токеном Kaggle.
Старый вызов `uv run python -m src.main` остаётся совместимым после установки.
`requirements.txt` оставлен как адаптер `pip install -e .`, но **не заменяет** lock-файл.

| Переменная ETL | По умолчанию | Назначение |
| --- | --- | --- |
| `KAGGLE_DATASET` | `sazzadsiddiquelikhon/myanimelist-anime-database-july-2025` | идентификатор датасета |
| `RAW_DATA_DIR` | `<RG_DATA_DIR>/raw` | скачанные CSV |
| `PROCESSED_DATA_DIR` | `<RG_DATA_DIR>/processed` | выход Parquet |
| `DATABASE_URL` | `sqlite:///<RG_DATA_DIR>/processed/anime.db` | SQLAlchemy URL базы |

Значения из `.env.example` соответствуют значениям по умолчанию при `RG_DATA_DIR=data`.
Для Jupyter локально: `uv sync --locked --extra etl --extra notebooks`, затем
`uv run jupyter lab`. Можно использовать `docker compose up --build`: порт опубликован
только на localhost, авторизация Jupyter **не отключается**; токен смотрите в логе.
Сборка Docker не входит в критерии ЛР1 и проверяется отдельно при наличии Docker.

## Сдача

Ссылка: https://github.com/WhyNot-png/anime-data-engineering

Краткий отчёт: [docs/lab1_report.md](docs/lab1_report.md).
После проверки зелёного CI итогового коммита на `main` поставьте тег сдачи:

```bash
git switch main
git pull --ff-only
git tag lab1
git push origin lab1
```

Не переносите уже опубликованный `lab1` на другой коммит: преподаватель должен
видеть неизменный срез проекта. Зелёный CI нужно проверять по реальному запуску,
а не только по наличию YAML или бейджа.
