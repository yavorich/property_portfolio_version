# Property Portfolio Bot

Telegram-бот для риелторов, который по ссылке на объявление с **Bayut** или **Property Finder** (площадки недвижимости ОАЭ) собирает данные об объекте, выкачивает фотографии, **снимает с них водяные знаки** агентств и присылает готовую PDF-презентацию для клиента.

Цикл «ссылка → готовый PDF» занимает ~30–60 секунд и проходит без участия человека.

---

## Что делает бот

Пользователь кидает в чат ссылку:

```
https://www.bayut.com/property/details-13898698.html
```

Бот в реальном времени редактирует одно и то же сообщение со статусами:

```
📥 Downloading listing page…
💾 Saving property data…
🖼 Downloading photos (28)…
🧹 Removing watermark (1/4)…
🧹 Removing watermark (2/4)…
…
✍️ Generating description…
📄 Building presentation…
✅ Done!
```

И в конце присылает PDF-файл `XE-R-0042.pdf` — обложка + слайды с характеристиками, фотографиями без чужих логотипов и ссылкой на исходное объявление.

Дополнительно бот умеет работать в режиме «лаборатории по очистке»: если кинуть ему просто фотографию (без ссылки), он удалит с неё ватермарку выбранным способом — это полезно для агента, когда нужно почистить фото руками вне основного пайплайна.

---

## Архитектурные решения, которые имеет смысл посмотреть

### 1. Pipeline-оркестратор с прозрачным статусом

Весь сквозной сценарий — [backend/apps/listings/services/pipeline.py](backend/apps/listings/services/pipeline.py).
Это один async-метод `process_url(url, user, on_status)`, в который передаётся колбэк `on_status: Callable[[str], Awaitable[None]]`. Все слои пайплайна (парсер, загрузчик фото, batch-удаление ватермарок, генерация описания, рендер PDF) дёргают его — а конкретно в случае Telegram-бота колбэк редактирует исходное сообщение пользователя. UI-слой полностью развязан с бизнес-логикой: ту же функцию можно подключить к веб-фронту или CLI.

Статусная машина листинга — `Listing.Status` ([backend/apps/listings/models.py:46](backend/apps/listings/models.py#L46)): `pending → parsing → downloading → parsed → processing → done | failed`. Поле в БД, видно в админке, удобно для разбора инцидентов.

### 2. Плагинная система парсеров

[backend/apps/listings/parsers/](backend/apps/listings/parsers/) — реестр парсеров по хосту:

```python
_REGISTRY: dict[str, type[Parser]] = {
    "bayut.com": BayutParser,
    "www.bayut.com": BayutParser,
    "propertyfinder.ae": PropertyFinderParser,
    "www.propertyfinder.ae": PropertyFinderParser,
}
```

Все парсеры реализуют `Protocol`-интерфейс `Parser` ([base.py](backend/apps/listings/parsers/base.py)) и возвращают единый dataclass `ParsedListing` — добавление третьего источника = ровно один файл + одна строка в реестре.

Внутри парсеров — реальная работа с грязными API:

* **Bayut** ([bayut.py](backend/apps/listings/parsers/bayut.py)) — раскладка иерархического адреса (`UAE → Dubai → Palm Jumeirah → The Crescent`), сборка URL фото из шаблона `thumbnails/{id}-800x600.jpeg` для объектов, где API не возвращает прямую ссылку, конверсия sqm↔sqft с детальным диагностическим логированием для отлова случаев, когда вендор меняет единицы измерения.
* **Property Finder** ([property_finder.py](backend/apps/listings/parsers/property_finder.py)) — толерантный разбор: вендор оборачивает payload в произвольное число уровней (`data → property → listing → result`), функция `_unwrap` разворачивает до 4 уровней. Площадь, цена, фотографии, контакты брокера собираются через каскад `_first_str(...)` по всем известным алиасам ключей.

### 3. Three-tier стратегия удаления ватермарок

[backend/apps/watermark/services/](backend/apps/watermark/services/) — три независимых движка плюс собственный OCR-детектор:

| Режим | Когда используется | Стек |
|---|---|---|
| `dewatermark` | По умолчанию в пайплайне — быстро, дёшево, автодетект | Dewatermark.ai API |
| `detect` | Точечная очистка — OCR находит координаты, Erase убирает только их | Tesseract → Stability AI Erase |
| `auto` | Резерв, когда OCR ничего не нашёл — генеративная замена по промпту | Stability AI Search-and-Replace |
| `mask` | Ручной режим — пользователь сам задаёт прямоугольник | Stability AI Erase |

OCR-детектор ([detector.py](backend/apps/watermark/services/detector.py)) — не просто tesseract-обёртка: он отфильтровывает текст по confidence, оставляет только боксы в «правдоподобных» для ватермарки зонах (низ кадра, углы, края — `BOTTOM_THRESHOLD`, `SIDE_THRESHOLD`), и **жадно мёржит соседние боксы**, чтобы один длинный URL не превратился в десяток отдельных масок:

```python
def _merge(boxes):
    # union прямоугольников с padding=10 пока есть пересечения
```

Маски для Stability собираются собственным кодом на Pillow ([mask.py](backend/apps/watermark/services/mask.py)) — поддерживается и геометрия в долях кадра (`x_ratio`, `y_ratio`, `w_ratio`, `h_ratio` — удобно при разных разрешениях), и набор bbox'ов от OCR. Есть debug-режим: бот может прислать превью с полупрозрачным красным прямоугольником поверх предполагаемой маски, чтобы подобрать координаты не вслепую.

В пайплайне обработка фото — batch с лимитом ([watermark_batch.py](backend/apps/listings/services/watermark_batch.py)): чистим только первые 4 фотографии (`PRESENTATION_PHOTO_COUNT`), которые реально попадут в PDF. Это сознательное ограничение — Dewatermark.ai тарифицируется поштучно, а обрабатывать 30 фото из листинга, когда в презентации показывается 4, нет смысла.

### 4. AI-генерация описания и фич через Claude

[backend/apps/listings/services/ai_description.py](backend/apps/listings/services/ai_description.py) — обращение к Anthropic API за двумя задачами:

* короткое маркетинговое описание (5–6 строк, ~70 слов) — переписывает «полотно» брокера в формат, читаемый на одной странице PDF;
* выжимка ключевых features (5–7 пунктов, 1–4 слова каждый, Title Case) — для блока «Особенности».

Обе задачи запускаются **параллельно через `asyncio.create_task`** из исходного длинного описания — иначе вторая получила бы уже сокращённый текст и потеряла бы детали. Ответ Claude парсится толерантно: терпит ```json``` code fences и trailing-текст, фильтрует по длине, валидирует структуру. Любая ошибка LLM = фолбэк на оригинальный текст из API, пайплайн не падает.

### 5. Прокси-роутинг

Bayut, PropertyFinder и Telegram заблокированы на хостинге в РФ. Решение — встроенный proxy fallback ([pipeline.py:86](backend/apps/listings/services/pipeline.py#L86), [run_polling.py](backend/run_polling.py)):

```python
async def _open_working_client(test_url, proxies):
    for proxy in proxies:
        client = _build_client(proxy, PAGE_TIMEOUT)
        response = await client.head(test_url, timeout=httpx.Timeout(10.0))
        if response.status_code < 500:
            return client, proxy
        await client.aclose()
```

Прокси читаются из текстового файла построчно (одна строка = один URL, поддержка SOCKS5). Перед стартом бота `_pick_working_proxy` прогоняет healthcheck `bot.get_me()` через каждый прокси и стартует на первом рабочем. В рантайме каждый листинг открывает свой клиент и тоже ищет рабочий прокси под конкретный хост.

Отдельная тонкость в [pipeline.py:113](backend/apps/listings/services/pipeline.py#L113): RapidAPI-хосты типа `b_yut-data-api.p.rapidapi.com` содержат подчёркивание, которое нарушает RFC 1035. Python-овский `ssl` рубит хэндшейк по hostname check, curl — пропускает. Поэтому SSL-контекст оставляет проверку chain of trust, но отключает hostname verify — найдено отладкой, прокомментировано в коде.

### 6. Полностью async-стек

Django 5.2 + ASGI (uvicorn), модели читаются/пишутся через `acreate / asave / async for`, HTTP — `httpx.AsyncClient`, Telegram — `python-telegram-bot 22` (async-first). Блокирующие участки (Pillow, pytesseract, pdfkit→wkhtmltopdf, Django FileField.save) изолированы через `asyncio.to_thread` — event-loop не встаёт, пока tesseract молотит OCR или wkhtmltopdf рендерит PDF.

### 7. Рендер PDF без headless-браузера

[backend/apps/listings/services/presentation.py](backend/apps/listings/services/presentation.py) — Django-шаблон → HTML → wkhtmltopdf через `pdfkit`. Преимущество перед Puppeteer/Playwright: не нужен Chromium в образе. wkhtmltopdf ставится одним deb-пакетом в [Dockerfile](Dockerfile), весь рендер занимает <1 сек на листинг.

Шаблон ([listings/listing_pdf.html](backend/apps/listings/templates/listings/listing_pdf.html)) — обложка с hero-фото + 3 thumbnails, страницы с характеристиками, описанием, контактом брокера и QR/ссылкой на оригинал. Подбор картинок предпочитает `processed` (без ватермарки) и фолбэчит на `original` — даже если Dewatermark.ai упал, PDF собирается.

### 8. Лимиты и cleanup

* **Per-user квота** ([handlers.py:270](backend/telegram_bot/handlers.py#L270)) — `PRESENTATION_LIMIT_PER_USER` (по умолчанию 3 успешные генерации). Счётчик берёт только `status=DONE` и уважает поле `user.generations_reset_at`, чтобы админ мог одним кликом обнулить лимит конкретному агенту.
* **Cleanup-таск** ([tasks.py](backend/apps/listings/tasks.py)) — Celery Beat раз в сутки удаляет фотофайлы и PDF старше 30 дней. Сами строки `Listing` остаются для истории, обнуляются только `FileField`-ссылки.

### 9. Кастомная админка на Unfold

В [backend/core/](backend/core/) — целый набор переиспользуемых расширений `django-unfold`: nested admin, sortable, singleton, autocomplete, user admin mixins, color/compressed-image model fields. Они вынесены в `core` именно как библиотека: каждое расширение — отдельный `INSTALLED_APP`, чтобы при копировании в другой Django-проект можно было взять только нужное.

Среди прочего — `BotSettings` (singleton-модель через `django-solo`): админ редактирует ссылку на саппорт, текст кнопки и контактный URL прямо из админки, бот подхватывает изменения без перезапуска.

---

## Стек

* **Python 3.12**, **Django 5.2** + DRF 3.16, ASGI через `uvicorn[standard]`
* **python-telegram-bot 22.1** (async)
* **httpx 0.27** + `socksio` — единственный HTTP-клиент во всём проекте
* **Pillow** + **pytesseract** — компьютерное зрение для OCR-детекции ватермарок
* **pdfkit** + **wkhtmltopdf** — рендер PDF из Django-шаблонов
* **PostgreSQL 15**, **Redis 7**, **RabbitMQ 3.10**
* **Celery 5.5** + **django-celery-beat** — периодические задачи
* **django-unfold** — современная админка
* Внешние API: **RapidAPI** (Bayut, Property Finder), **Dewatermark.ai**, **Stability AI** (Erase / Search-and-Replace), **Anthropic Claude**
* Деплой: **Docker Compose** + **Nginx** (reverse proxy + раздача статики/media)

---

## Структура проекта

```
backend/
├── apps/
│   ├── account/           # Telegram-пользователи + админ-юзеры
│   ├── listings/
│   │   ├── parsers/       # Плагины под Bayut и Property Finder
│   │   ├── services/
│   │   │   ├── pipeline.py          # Главный оркестратор «ссылка → PDF»
│   │   │   ├── watermark_batch.py   # Batch-очистка фото листинга
│   │   │   ├── ai_description.py    # Claude: описание + features
│   │   │   └── presentation.py      # Рендер PDF из Django-шаблона
│   │   ├── templates/listings/
│   │   ├── models.py      # Listing, ListingPhoto, BotSettings
│   │   └── tasks.py       # Celery: cleanup старых медиа
│   └── watermark/
│       └── services/
│           ├── pipeline.py     # 4 режима: dewatermark / detect / auto / mask
│           ├── detector.py     # OCR (tesseract) + фильтр зон + merge bbox
│           ├── mask.py         # Pillow: маски и overlay-превью
│           ├── stability.py    # Stability AI Erase / Search-and-Replace
│           └── dewatermark.py  # Dewatermark.ai
├── telegram_bot/
│   ├── handlers.py        # Все хендлеры: /start, /help, photo, text
│   ├── proxies.py         # Загрузка прокси-листа
│   └── django_setup.py    # Bootstrap Django из standalone-скрипта
├── core/                  # Переиспользуемая «библиотека» расширений
│   ├── unfold_admin/
│   ├── unfold_nested/
│   ├── unfold_singleton/
│   ├── adrf/              # Async DRF mixins/viewsets
│   └── …
├── config/                # Django settings + Celery + ASGI/WSGI
└── run_polling.py         # Точка входа бота (отдельный контейнер)

docker-compose.yml         # nginx + backend + bot + postgres + redis + rabbitmq + celery + celery-beat
Dockerfile                 # python:3.12-slim + wkhtmltopdf + tesseract
```

---

## Локальный запуск

Нужны Docker и `make`.

```bash
cp .env.example .env   # заполнить ключами от RapidAPI / Dewatermark / Stability / Anthropic / Telegram
make build
make up
make migrate
docker exec -it backend python manage.py createsuperuser
```

После старта поднимаются:

* `bot` — Telegram-бот в polling-режиме (можно тестировать в Telegram сразу)
* `backend` — Django admin на `http://localhost/admin/`
* `celery` + `celery-beat` — фоновые задачи (cleanup)

Полезные команды из [Makefile](Makefile): `make logs c=bot`, `make app-bash`, `make psql`, `make restart-celery`.

### Минимальный набор env-переменных

```
SECRET_KEY=...
ALLOWED_HOSTS=localhost
CORS_ORIGIN_WHITELIST=http://localhost

POSTGRES_DB=portfolio
POSTGRES_USER=postgres
POSTGRES_PASSWORD=...
POSTGRES_HOST=postgres
POSTGRES_PORT=5432

REDIS_HOST=redis
REDIS_PORT=6379

RABBITMQ_HOST=rabbitmq
RABBITMQ_PORT=5672
RABBITMQ_USER=guest
RABBITMQ_PASSWORD=guest

TELEGRAM_BOT_TOKEN=...
TELEGRAM_PROXY_FILE=/backend/proxies.txt   # опционально

BAYUT_API_KEY=...
PROPERTYFINDER_API_KEY=...
DEWATERMARK_API_KEY=...
STABILITY_API_KEY=...
ANTHROPIC_API_KEY=...
ANTHROPIC_MODEL=claude-haiku-4-5

PRESENTATION_LIMIT_PER_USER=3
```

---

## Что я хотел показать этим проектом

* Сквозной пайплайн «грязный внешний источник → чистый продукт» с реальной обработкой ошибок на каждом шаге (упавший прокси, флапающий API, неконсистентные ключи в payload, поломанный OCR), а не happy-path-демо.
* Композицию нескольких внешних сервисов под одну задачу с понятной стратегией fallback'ов (4 движка под одну операцию «убрать ватермарку»).
* Полностью async Django-приложение, где блокирующие участки явно изолированы.
* Подход к расширяемости — добавить третью площадку = один файл, добавить пятый режим очистки = один файл.
* Эксплуатационные мелочи, без которых продукт не выживает в реальности: статус-машина листинга в БД, прокси-роутинг с healthcheck'ами, лимиты по пользователю, периодический cleanup медиа, детальное логирование на каждом шаге.
