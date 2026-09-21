# MyAnimeList Data Engineering Project

Шаблон учебного проекта по Python и инженерии данных на основе датасета [MyAnimeList Anime Database — July 2025](https://www.kaggle.com/datasets/sazzadsiddiquelikhon/myanimelist-anime-database-july-2025).

## Структура

- `src/extract.py` — загрузка датасета с Kaggle
- `src/transform.py` — очистка и преобразование CSV
- `src/load.py` — загрузка результата в SQLite
- `src/main.py` — запуск ETL-пайплайна
- `notebooks/` — Jupyter-ноутбуки
- `data/raw/` и `data/processed/` — локальные данные (не добавляются в Git)
- `tests/` — тесты

## Быстрый запуск

1. Установить Python 3.11+.
2. Создать виртуальное окружение:

```bash
python -m venv .venv
```

3. Активировать его:

```bash
# Windows
.venv\Scripts\activate

# Linux/macOS
source .venv/bin/activate
```

4. Установить зависимости:

```bash
pip install -r requirements.txt
```

5. Настроить Kaggle API: скачать `kaggle.json` в настройках аккаунта Kaggle и положить его в `~/.kaggle/kaggle.json`.
6. Запустить пайплайн:

```bash
python -m src.main
```

Результат появится в `data/processed/anime.db`.

## Запуск в Docker

```bash
docker compose up --build
```

JupyterLab будет доступен по адресу `http://localhost:8888`.

## Проверка

```bash
pytest
```

> Файлы данных и секреты Kaggle не должны попадать в репозиторий.
