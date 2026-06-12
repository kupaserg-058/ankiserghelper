# Ankibot

Личный Telegram-бот для создания флеш-карточек из любого материала с помощью
Gemini AI и их изучения через интервальное повторение (алгоритм SM-2).

## Возможности

- Создание колод карточек из:
  - 📄 PDF-файлов
  - 🔗 ссылок на статьи (Habr, Medium и др.)
  - 📺 YouTube и других видео/аудио (через yt-dlp + транскрипция Gemini)
  - 🎙 голосовых сообщений Telegram
  - ✏️ обычного текста
- Автогенерация карточек трёх типов: flashcard, multiple_choice, open_question
- Интервальное повторение по алгоритму SM-2
- Проверка развёрнутых ответов через Gemini
- Статистика прогресса

## Получение ключей

### Telegram Bot Token
1. Напиши [@BotFather](https://t.me/BotFather) в Telegram
2. `/newbot` → следуй инструкциям → получишь токен вида `123456:ABC-DEF...`

### Google Gemini API Key
1. Перейди на [aistudio.google.com](https://aistudio.google.com/apikey)
2. Войди с Google-аккаунтом → "Create API key"
3. Бесплатный tier: 1500 запросов/день, 15 запросов/минуту, 1M токенов контекста

### Свой Telegram ID
1. Напиши [@userinfobot](https://t.me/userinfobot) — он пришлёт твой ID
2. Укажи его в `ALLOWED_USER_IDS` (через запятую, если несколько пользователей)

## Запуск

```bash
cp .env.example .env
# заполни .env: TELEGRAM_TOKEN, GOOGLE_API_KEY, ALLOWED_USER_IDS

docker compose up -d --build
```

Миграции БД применяются автоматически при старте контейнера `bot`.

Логи:
```bash
docker compose logs -f bot
```

## Команды бота

- `/start` — приветствие
- `/help` — справка
- `/new` — создать новую колоду карточек
- `/decks` — список колод
- `/review` — повторить карточки, у которых наступил срок (все колоды)
- `/review <id>` — повторить конкретную колоду
- `/stats` — статистика

## Архитектура

```
bot/
├── main.py            # точка входа: Bot, Dispatcher, polling
├── config.py          # настройки из .env
├── db.py               # async SQLAlchemy engine/session
├── handlers/           # роутеры aiogram (команды, FSM-флоу)
├── services/
│   ├── gemini.py        # генерация карточек и проверка ответов (google-genai)
│   ├── parser.py         # PDF / URL / YouTube / голос → материал
│   └── sm2.py            # алгоритм интервального повторения SM-2
├── models/              # SQLAlchemy модели (User, Deck, Card, CardReview, ReviewSession)
├── repositories/        # слой доступа к БД
├── keyboards/           # inline-клавиатуры
└── middlewares/         # auth (allowlist), throttling, db session
alembic/                # миграции БД
```

## Технический стек

- Python 3.12, aiogram 3.x
- google-genai (модель `gemini-2.5-flash` по умолчанию, бесплатный tier)
- PostgreSQL + SQLAlchemy (async) + Alembic
- Redis (FSM-хранилище и троттлинг)
- yt-dlp + ffmpeg (аудио из видео)
- pdfplumber (fallback для больших PDF), httpx + BeautifulSoup (статьи)
