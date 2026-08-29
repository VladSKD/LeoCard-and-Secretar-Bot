# CLAUDE.md — Project guide for AI assistants

## What this is

Monorepo for Telegram bots run by the NULP (Lviv Polytechnic) student union (profkom). Three bots share one Docker Compose stack deployed on a single AWS EC2 t3.micro via a self-hosted GitHub Actions runner. A fourth bot (tickets) is planned for inclusion but currently lives in a separate repo.

## Language

All user-facing text, comments in bot code, and variable names in the bots are in **Ukrainian**. Commit messages, docs, and infra code are in English. When writing code or messages shown to users, use Ukrainian.

## Repository layout

```
monorepo/
├── bots/
│   ├── leocard/       # python-telegram-bot 20+ — student transit card application with OCR
│   ├── newbie/        # python-telegram-bot 21.6 — info bot for university applicants
│   └── profcom/       # aiogram 3.x + Google Gemini — petition generator (DOCX from free-form text)
├── shared/            # Tiny Python package mounted into all containers
│   ├── logging_config.py   # setup_logging(bot_name) — stdout, 12-factor
│   └── notifications.py    # Read-only helper for notification_chats.json
├── data/              # Host-side persistent state (git-ignored)
│   ├── leocard/       # credentials.json, token.json, bot_persistence/
│   ├── profcom/       # credentials.json, token.json, generated_petitions/
│   ├── shared/        # notification_chats.json
│   └── tickets/       # service_account.json (placeholder for future)
├── infrastructure/terraform/   # VPC + EC2 + SG (Terraform)
├── .github/workflows/deploy.yml
├── docker-compose.yml
├── Makefile
├── .env.example
└── docs/DEPLOY.md     # EC2 setup, runner install, credential generation
```

## Bot details

### leocard (`bots/leocard/`)
- **Framework**: python-telegram-bot 20+
- **Entry**: `main.py` — ConversationHandler-based FSM
- **Config**: `config.py` — BotConfig, GoogleConfig, FileNames, Messages, Buttons classes
- **Key services**: `services/ocr.py` (Tesseract), `services/google_services.py` (Drive + Sheets), `services/pdf.py`, `services/scanner.py`, `services/validators.py`
- **Google auth**: OAuth 2.0 user credentials (`credentials.json` + `token.json` bind-mounted)
- **State**: PicklePersistence in `data/leocard/bot_persistence/`
- **System deps**: tesseract-ocr, libgl1 (OpenCV) — see Dockerfile

### newbie (`bots/newbie/`)
- **Framework**: python-telegram-bot 21.6
- **Entry**: `bot.py` — stateless, callback-query navigation
- **No Google APIs**, no persistence, no external deps beyond Telegram
- **Handlers** in `handlers/` — each file covers one menu section (bachelor, master, dormitories, contacts, etc.)
- **Data**: `institutes.py` — large dict of institute info (hardcoded)

### profcom (`bots/profcom/`)
- **Framework**: aiogram 3.x
- **Entry**: `main.py` — aiohttp health-check server + aiogram polling
- **AI**: `ai_processor.py` — Google Gemini API for parsing free-form petition text
- **Documents**: `docx_processor.py` + `create_templates.py` — generates DOCX petitions from templates in `templates/`
- **Google auth**: OAuth 2.0 user credentials (same pattern as leocard)
- **Config**: `config.py` — reads env vars directly (BOT_TOKEN, GEMINI_API_KEY, etc.)
- **Health endpoint**: port 10000, exposed only on localhost

## How secrets work

`.env` stores prefixed names (`LEOCARD_TELEGRAM_BOT_TOKEN`, `PROFCOM_TELEGRAM_BOT_TOKEN`, etc.). `docker-compose.yml` remaps them to plain names each bot expects. **Bot code does NOT know it's in a monorepo** — it reads the same env var names as before.

Google OAuth files are bind-mounted from `data/<bot>/` — NOT stored in env vars.

## Key commands

```bash
make init       # Create data dirs, .env, placeholder files
make doctor     # Verify secrets are in place
make up         # docker compose up -d
make down       # docker compose down
make logs       # Tail all bots
make logs-<bot> # Tail one bot (leocard|newbie|profcom)
make rebuild    # No-cache build + restart
```

## Deploy flow

`git push origin main` → GitHub Actions runner on EC2 → checkout → symlink secrets from `/etc/telegram-bots/` → `docker compose build` → `docker compose up -d` → smoke-test containers.

See `docs/DEPLOY.md` for full details and `infrastructure/terraform/` for AWS resources.

## Coding conventions

- **Don't unify frameworks**. leocard/newbie use python-telegram-bot, profcom uses aiogram. This is intentional.
- Each bot has its own `requirements.txt` and `Dockerfile` — deps are isolated.
- `shared/` is read-only inside containers. Only add things ALL bots need.
- When adding env vars: add to `.env.example` with prefix, remap in `docker-compose.yml`.
- Bot entrypoints: leocard=`main.py`, newbie=`bot.py`, profcom=`main.py`.
- All text shown to Telegram users must be in Ukrainian.

## TODOs / known gaps

- `bots/tickets/` does not exist yet — the tickets bot is still in a separate repo (`../tickets-bot/`). It's designed for a separate EC2 but the monorepo README references it.
- `shared/logging_config.py` — done (stdout, 12-factor), but some bots still use their own `logging.basicConfig()` instead of `setup_logging()`.
- newbie bot's `bot.py` still calls `logging.basicConfig()` directly instead of using `shared.logging_config`.

## Don't touch

- `data/` — git-ignored, host-specific secrets and state
- `infrastructure/terraform/terraform.tfstate` — should not be committed (but is; don't delete it without moving state elsewhere)
- `.env` — real secrets, git-ignored
- Google credential/token JSON files
