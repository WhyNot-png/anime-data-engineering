# Бизнес-правила

Правила живут в `app/services/`, обработчики эндпоинтов только вызывают сервисы.
Каждое правило покрыто тестами; нарушение возвращает `409 Conflict` (или `422`,
если запрос некорректен по форме).

## BR-1. Один тайтл — одна запись в списке просмотра

Повторное добавление тайтла пользователем отклоняется с `409`
«Этот тайтл уже добавлен в список просмотра».
Реализация: `app/services/watchlist.py::add_entry`, `UNIQUE(user_id, anime_id)`.
Тесты: `test_watchlist_prevents_duplicates`, `test_watchlist_flow_with_autocompletion`.

## BR-2. Прогресс ограничен числом эпизодов, конец просмотра автозавершает тайтл

- `progress > episodes` → `409` («Прогресс N превышает число эпизодов (M)»).
- `progress == episodes` → статус автоматически становится `completed`.
- `progress > 0` при статусе `planned` → статус становится `watching`.
- `status=completed` с недосмотренными эпизодами → `409`.
- `status=watching` с `progress=0` → `422`.
- Если число эпизодов неизвестно (`episodes IS NULL` или `0`), верхней границы нет.

Реализация: `_validate_progress`, `_resolve_status`.
Тесты: `test_watchlist_autocompletes_on_last_episode`,
`test_watchlist_rejects_progress_over_episodes`,
`test_watchlist_completed_requires_all_episodes`,
`test_watchlist_watching_requires_progress`,
`test_watchlist_unknown_episode_count_is_unbounded`.

## BR-3. Отзыв — только после полного просмотра и только один

Отзыв доступен, если у пользователя есть запись со статусом `completed`.
Иначе `409`: «Сначала добавьте тайтл в список просмотра» / «Отзыв можно оставить
только после полного просмотра (completed)». Второй отзыв на тот же тайтл → `409`.
Реализация: `app/services/reviews.py::create_review` + `require_completed`.
Тесты: `test_review_requires_completed_status`, `test_review_unique_per_user`,
`test_reviews_require_completed_and_are_unique`.

## BR-4. Тайтл с отзывами удалить нельзя

Удаление возвращает `409` с числом отзывов: история оценок не теряется.
Студию, к которой привязаны тайтлы, тоже удалить нельзя (`409`).
Реализация: `app/services/catalog.py::delete_anime`, `app/api/dictionaries.py::delete_studio`.
Тесты: `test_delete_anime_blocked_by_reviews`, `test_delete_anime_without_reviews`,
`test_dictionaries`.

## BR-5. Агрегаты считаются по актуальным отзывам

Средняя оценка и число отзывов считаются подзапросом, а не хранимым полем,
поэтому не расходятся с данными. Топ-N учитывает только тайтлы с
`reviews_count >= min_reviews`, чтобы один отзыв не выводил тайтл в лидеры.
Реализация: `app/services/analytics.py`, `app/services/catalog.py::_rating_subquery`.
Тесты: `test_analytics_top_anime_and_genres`, `test_analytics_year_stats`,
`test_top_anime_endpoint`.
