# ETL: импорт каталога из CSV

## Запуск

```bash
# локально
python -m app.etl.import_anime --source data/anime.csv --report logs/etl-report.json

# в контейнере (выполняется автоматически при docker compose up)
docker compose exec api python -m app.etl.import_anime --source data/anime.csv
```

Код выхода: `0` — успех, `2` — файл не найден или CSV без обязательной колонки `title`.

## Этапы

1. **Extract** — `read_csv` читает UTF-8 (BOM допускается), проверяет заголовок.
2. **Validate/Clean** — `clean_row` для каждой строки:
   - нормализация пробелов, `\ufeff`, HTML-мусора;
   - `title` обязателен, длина 1–300, иначе `missing_title` / `title_too_long`;
   - `mal_id`, `year` (1900–2100), `episodes` (0–10000) — целые числа,
     иначе `bad_number` / `out_of_range`;
   - `status` приводится из алиасов MAL (`Finished Airing`, `Currently Airing`,
     `Not yet aired`), неизвестное значение → `bad_status`;
   - `genres` разбиваются по `;`, `|`, `,`, приводятся к Title Case, дубликаты
     внутри строки удаляются;
   - `synopsis` обрезается до 4000 символов.
3. **Transform** — дубликаты отбрасываются по `mal_id`, а при его отсутствии
   по названию без учёта регистра.
4. **Load** — в одной транзакции: студии и жанры создаются по требованию,
   тайтл обновляется по `mal_id` (или по названию), связи `anime_genres`
   перезаписываются.

## Идемпотентность

Повторный запуск не создаёт дубликатов: второй прогон даёт
`created: 0, updated: N` при том же числе строк в БД. Проверяется тестом
`test_second_run_is_idempotent` и шагом CI «ETL и seed на PostgreSQL».

## Логирование

В stdout: строка итога и предупреждения по каждой причине отказа.
В JSON-отчёт (`logs/etl-report.json`):

```json
{
  "source": "data/anime.csv",
  "rows_in_file": 17,
  "accepted": 14,
  "rejected": 2,
  "duplicates_skipped": 1,
  "created": 14,
  "updated": 0,
  "rejection_reasons": { "missing_title": 1, "out_of_range": 1 },
  "rejections": [{ "row": 16, "reason": "missing_title", "detail": "пустое название" }],
  "db_totals": { "anime": 14, "studios": 11, "genres": 9 }
}
```

## Демо-данные

`python scripts/seed.py` — импорт `data/anime.csv` + три пользователя, пять записей
списка просмотра и четыре отзыва, чтобы аналитика и интерфейс были не пустыми.
Скрипт идемпотентен.
