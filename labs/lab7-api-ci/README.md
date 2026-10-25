# Задание 7. Тестирование, контейнеризация и CI/CD FastAPI

![CI](https://github.com/WhyNot-png/anime-data-engineering/actions/workflows/ci.yml/badge.svg?branch=main)

Продолжение [сервиса из задания 6](../lab6-task-manager/README.md).
Исходный код не дублируется: приложение, тесты, Dockerfile, pytest.ini и Compose
находятся в `labs/lab6-task-manager`. Корневой workflow `.github/workflows/ci.yml`
сохраняет прежнюю матрицу качества и добавляет job-ы `lint`, `test`, `build`.

## Выполнено и границы результата

- 41 тест API на настоящем PostgreSQL; порог покрытия приложения 80%.
- Ровно девять отдельных именованных приёмочных тестов соответствуют всем пунктам шага 4.
- Многоэтапный Dockerfile: runtime-deps, test-deps, runtime, test; UID/GID 10001.
- Compose: приложение `app`, рабочая БД `db`, отдельная `test-db`, контейнер `tests`.
- Все push и pull_request запускают линтер/тесты. Публикация — только push main после успеха.
- Реальный красный PR, исправленный зелёный запуск, merge и публикация в GHCR и Docker Hub подтверждены ниже.

**Оба реестра опубликованы.** После настройки repository secrets запуск
[CI 40246205211](https://github.com/WhyNot-png/anime-data-engineering/actions/runs/40246205211)
завершился успешно. Публичная доступность Docker Hub дополнительно проверена
анонимным запросом API: HTTP 200 для тега полного SHA. Ранние запуски без
учётных данных сохранены ниже как история настройки, а не текущее ограничение.

## 1. Обязательные тесты

[Файл test_required_cases.py](../lab6-task-manager/tests/test_required_cases.py).

| № | Отдельный тест | Проверка |
| --- | --- | --- |
| 1 | test_01_create_user_201 | Создание пользователя, id и email |
| 2 | test_02_duplicate_email_409 | Повторный email и сообщение ошибки |
| 3 | test_03_invalid_email_422 | Невалидный email и ошибка поля |
| 4 | test_04_create_task_201 | Задача создана, владелец и done=false |
| 5 | test_05_missing_owner_404 | Несуществующий владелец |
| 6 | test_06_done_filter_and_pagination | done=false, limit=1, offset=1, точный ожидаемый id |
| 7 | test_07_patch_changes_only_provided_fields | Меняется done, остальные поля прежние |
| 8 | test_08_delete_then_get_404 | Пустой 204 и последующий 404 |
| 9 | test_09_process_time_header | X-Process-Time присутствует и неотрицателен |

Ещё 32 теста из задания 6 проверяют другие границы и сценарии.
[Локальный лог](evidence/pytest.txt): **41 passed**, покрытие строк/ветвей **83,86%**.
В этом локальном замере использован PostgreSQL 16 нативно на порту 55432;
прохождение Docker-тестов подтверждается отдельно фактическими запусками CI.

Фикстуры отклоняют БД без суффикса `_test`. Перед каждым API-тестом проверяется,
что таблицы пусты; внешняя транзакция + SAVEPOINT откатывают изменения, включая
commit внутри роутера. Загрязнённая БД вызывает явную ошибку, а не удаляется молча.
Сессия подменяется через `app.dependency_overrides[get_session]`; после теста
подмена снимается. `create_all` не используется, схема создаётся Alembic.

## 2. Запуск локальных тестов

Нужны Docker Compose v2, uv 0.13.5 и Python 3.12.12. Команды Bash:

```bash
git clone https://github.com/WhyNot-png/anime-data-engineering.git
cd anime-data-engineering/labs/lab6-task-manager
uv sync --locked
# Только отдельная тестовая БД; рабочая tasks не затрагивается.
docker compose --profile test up -d test-db
DATABASE_URL=postgresql+asyncpg://app:app@localhost:5433/tasks_test uv run alembic upgrade head
TEST_DATABASE_URL=postgresql+asyncpg://app:app@localhost:5433/tasks_test uv run pytest
uv run ruff check .
uv run ruff format --check .
```

В PowerShell задавайте переменные отдельно через `$env:DATABASE_URL="..."` и
`$env:TEST_DATABASE_URL="..."`. Верните DATABASE_URL основной БД после миграции.
Без uv: venv + `pip install -r requirements-dev.txt`, далее `python -m pytest`.

## 3. Тесты полностью через Docker Compose

Из того же каталога, без локальной установки Python:

```bash
docker compose --profile test run --build --rm tests
# Нулевой код завершения означает успех; код pytest не маскируется.
```

Compose ждёт healthcheck отдельной PostgreSQL `test-db`. Тестовый контейнер от
UID 10001 применяет `alembic upgrade head`, затем выполняет `python -m pytest`.
Нет bind-mount всего репозитория или доступа к рабочей БД. Для удаления только
временной тестовой БД без остановки рабочего app/db:

```bash
docker compose stop test-db
docker compose rm -f test-db
```

Не выполняйте `docker compose down -v` для обычной очистки тестов: эта команда
может удалить именованный том с рабочей БД `tasks`.

## 4. Приложение и устройство образов

```bash
cp .env.example .env
docker compose up -d --build app
# Swagger UI: http://localhost:8000/docs
docker compose logs app
```

`app` ждёт готовность `db` по `pg_isready`, затем применяет миграции и запускает API.
Это учебная стратегия запуска одного экземпляра; для production миграции следует
выносить в отдельную CD-задачу (см. ответы).

```bash
# Только runtime-образ: обязательно указать target, последний stage — test.
docker build --target runtime -t anime-task-manager:local .
docker run --rm --entrypoint id anime-task-manager:local -u
# Ожидается 10001.
```

В runtime скопирована только venv с рабочими зависимостями: pytest/ruff и тестов
там нет. Test stage получает отдельную venv с dev-зависимостями и рабочий каталог
`/workspace`, доступный непривилегированному пользователю. Пароли/`.env` не попадают
в build context благодаря `.dockerignore`; URL приходит через окружение.

## 5. Конвейер CI/CD

[ci.yml](../../.github/workflows/ci.yml):

```text
push / pull_request
  ├── quality: прежняя матрица Python 3.12/3.13 × Ubuntu/Windows
  └── lint: ruff check + ruff format
        └── test: multistage test image + PostgreSQL + Alembic + pytest
              └── build (needs: lint, test, quality; только push main)
                    ├── runtime build + проверка UID=10001
                    ├── push GHCR: latest и полный SHA
                    └── push Docker Hub: latest и полный SHA (нужны secrets)
```

На PR, в том числе из форка, образы не публикуются и registry-секреты не нужны.
При неудаче lint/test/quality job build пропускается из-за `needs` и стандартного
условия успеха. GitHub Packages write разрешён только job-у build, остальным —
contents:read. Docker login получает токен через stdin, а не аргумент командной
строки. В конце выполняется logout. Образы имеют OCI source label со ссылкой на репозиторий.

## 6. Реальная проверка «красный PR → исправление → merge»

Создан [PR №3](https://github.com/WhyNot-png/anime-data-engineering/pull/3).
Первый коммит `dfab1d9c` намеренно ожидал 418 вместо 201 только в
`test_01_create_user_201`. [CI pull_request 40244404795](https://github.com/WhyNot-png/anime-data-engineering/actions/runs/40244404795)
реально завершился Failure: job `API PostgreSQL tests` вернул exit code 1,
качество и lint прошли, build пропущен. На PR публикация также запрещена отдельным if,
поэтому один этот скриншот не доказывает, что причиной пропуска build был только needs.

![Намеренно упавший pipeline PR](screenshots/pipeline-failure.svg)

[Протокол CI](evidence/pr-failure.json) и
[локальное воспроизведение той же ошибки](evidence/intentional-failure-local.txt):
`assert 201 == 418`, 1 failed, 40 passed. Полный runner log в анонимном интерфейсе
GitHub требует входа, поэтому локальный вывод не назван выгрузкой лога раннера.

В этом же PR ожидание исправлено на 201, коммит `7ec01bc83e676a05f372b503bb708eac21617658`.
[Повторный CI 40244740475](https://github.com/WhyNot-png/anime-data-engineering/actions/runs/40244740475)
завершился **Success**: API lint, PostgreSQL Docker-тесты и все 4 job прежней матрицы
зелёные. Build здесь корректно пропущен, потому что это не push main.

![Успешный pipeline исправленной ветки PR](screenshots/pipeline-success-pr.svg)

После зелёного запуска [PR №3 слит](https://github.com/WhyNot-png/anime-data-engineering/pull/3),
merge-коммит `3d3ed241b56484cf0d8c558a38e3f456ae341e8d`. Ошибочный тест не попал
в итоговое содержимое main. Для публикации образов проверяется отдельный запуск
этого merge-коммита на main, а не этот скриншот со skipped build.

### Первый успешный pipeline main: публикация GHCR до настройки Docker Hub

[CI 40244902812](https://github.com/WhyNot-png/anime-data-engineering/actions/runs/40244902812)
на merge-коммите завершился **Success**, включая job `Build and publish images`.
Контейнер прошёл проверку UID=10001, GHCR опубликован. **В этом раннем запуске Docker Hub ещё не опубликован**:
внизу скриншота сохранено реальное предупреждение об отсутствии secrets.
Это не замаскировано зелёным статусом общего pipeline.

![Успешный main pipeline с публикацией GHCR](screenshots/pipeline-success-main.svg)

| Этап | Коммит | Результат | Ссылка |
| --- | --- | --- | --- |
| PR с неверным ожиданием | dfab1d9c | Failure, API PostgreSQL tests exit 1 | [40244404795](https://github.com/WhyNot-png/anime-data-engineering/actions/runs/40244404795) |
| Исправленная ветка PR | 7ec01bc8 | Success, build skipped вне main | [40244740475](https://github.com/WhyNot-png/anime-data-engineering/actions/runs/40244740475) |
| Merge main | 3d3ed241 | Success, GHCR опубликован, Docker Hub отсутствует | [40244902812](https://github.com/WhyNot-png/anime-data-engineering/actions/runs/40244902812) |
| После настройки secrets | b6782fb6 | Success, оба реестра опубликованы; Docker Hub API HTTP 200 | [40246205211](https://github.com/WhyNot-png/anime-data-engineering/actions/runs/40246205211) |


## 7. Реестры образов

### GHCR

**Опубликованный публичный образ:**
[GitHub Packages / anime-task-manager](https://github.com/WhyNot-png/anime-data-engineering/pkgs/container/anime-task-manager).

Имя: `ghcr.io/whynot-png/anime-task-manager`. Есть теги `latest` и полный SHA
коммита. Для точного повторения проверенной публикации:

```bash
docker pull ghcr.io/whynot-png/anime-task-manager:3d3ed241b56484cf0d8c558a38e3f456ae341e8d
# Эквивалентная неизменяемая ссылка по digest
docker pull ghcr.io/whynot-png/anime-task-manager@sha256:7f308e677c438447143b1fba21245895f61a6e34bb8d24195f015611e1f91c0e
```

Анонимный запрос к registry manifest вернул **HTTP 200**; это отдельная проверка,
а не вывод только из зелёного CI. Страница пакета также доступна с HTTP 200.
[Машинный протокол](evidence/registry-publication.json). Для GHCR использован
автоматический `GITHUB_TOKEN`; личный PAT не передавался и не сохранялся.
`latest` будет обновляться последующими push main; SHA и digest фиксируют конкретный образ.

### Docker Hub

**Опубликованный публичный образ:**
[churovaa/anime-task-manager](https://hub.docker.com/r/churovaa/anime-task-manager).

Проверенный тег: `b6782fb6147121ca92127b68d91035caaf1e210b`.
Анонимный запрос Docker Hub API к этому тегу вернул **HTTP 200**.
Digest: `sha256:213ee95b73838f4e7fc1387a204baf4fff78963653dffed11038d12912288ea0`.
[Протокол проверки](evidence/dockerhub-publication.json).

```bash
docker pull churovaa/anime-task-manager:b6782fb6147121ca92127b68d91035caaf1e210b
# Неизменяемая ссылка по содержимому
docker pull churovaa/anime-task-manager@sha256:213ee95b73838f4e7fc1387a204baf4fff78963653dffed11038d12912288ea0
```

Публикация подтверждена успешным [запуском CI](https://github.com/WhyNot-png/anime-data-engineering/actions/runs/40246205211)
и независимой проверкой публичного тега. `latest` обновляется при следующих push main;
для воспроизводимости используются полный SHA или digest.

Учётные данные хранятся в GitHub Actions repository secrets:
`DOCKERHUB_USERNAME` и `DOCKERHUB_TOKEN`. Токен не включён в репозиторий
или отчёт. Публикация выполняется только после успешных проверок при push main,
не при pull_request или workflow_dispatch.

## 8. Ответы на контрольные вопросы

1. **CI / continuous delivery / continuous deployment.** CI проверяет интеграцию
   изменений автоматическими линтерами, тестами и сборкой. Continuous delivery
   подготавливает проверенный результат к выпуску с ручным решением о выпуске;
   continuous deployment автоматически развёртывает каждое прошедшее изменение.
   Наш workflow автоматически публикует образ, но не развёртывает production API.
2. **dependency_overrides.** Это словарь соответствий «исходная функция зависимости
   → тестовая функция». FastAPI при разрешении Depends вызывает подмену, поэтому
   роутер получает транзакционно изолированную тестовую сессию без изменения кода
   роутера. Подмену нужно обязательно снимать после теста.
3. **Многоэтапная сборка.** Сборочные/тестовые зависимости отделяются от финального
   runtime. В итоговый образ копируются только нужные артефакты/venv: меньше лишних
   пакетов и поверхность атаки. Этапы также позволяют переиспользовать слой зависимостей.
4. **Почему не root.** Уязвимость процесса от root повышает возможный ущерб внутри
   контейнера и при ошибочных mounts/настройках host. UID 10001 снижает привилегии,
   но не заменяет остальные меры: обновления, ограничения capabilities, секретов
   и доступа к Docker socket; socket в контейнер приложения не передаётся.
5. **Секреты в Actions.** Они хранятся в repository/environment secrets и передаются
   конкретному шагу через `${{ secrets.NAME }}` в env/stdin. В Git они остались бы
   в истории и клонах; маскирование логов не заменяет запрет на вывод секретов.
   Утёкший токен нужно отозвать, а не просто удалить новым коммитом.
6. **Если test упал.** Build не стартует: `needs: [lint, test, quality]` требует
   успешного завершения зависимостей. Дополнительно `if` разрешает публикацию
   только для push основной ветки. `always()` для build не используется.
7. **Где миграции.** На старте контейнера просто для учебного одиночного сервиса,
   но старт зависит от БД, требуются DDL-права, а несколько реплик могут запустить
   миграцию одновременно. Отдельный шаг CD даёт контролируемый однократный запуск
   и отдельные права/логи, но требует оркестрации и совместимости старого/нового кода
   со схемой; резервные копии и ручная проверка миграций нужны в обоих вариантах.
