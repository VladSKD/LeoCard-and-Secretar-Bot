# Telegram bots monorepo

Four independent Telegram bots unified under a single repository, deploy
pipeline, and infrastructure definition. Deployed on a self-hosted GitHub
Actions runner on EC2.

| Bot | Framework | Purpose |
|---|---|---|
| **leocard** | `python-telegram-bot` 20+ | Student transit-card ("ЛеоКарт") application flow with OCR of passport/tax ID, automatic upload to Google Drive/Sheets. |
| **newbie** | `python-telegram-bot` 21.6 | Stateless information bot for NULP applicants — institutes, admission rules, dormitories, contacts. |
| **profcom** | `aiogram` 3.x + Google Gemini | Generates formal petitions (клопотання) as DOCX from free-form Ukrainian text. |
| **tickets** | `aiogram` 3.x | Sells event tickets: buyer walks a short form, uploads a payment screenshot, admins approve/reject with inline buttons, status and metadata land in Google Sheets. |

Each bot lives in its own folder with its own `Dockerfile` and
`requirements.txt`. They share nothing at the code level except the small
`shared/` package (logging config). They share everything at the infra level:
one docker-compose, one `.env`, one Terraform stack, one GitHub Actions
deploy workflow.

## Repository layout

```
monorepo/
├── README.md                   ← you are here
├── Makefile                    ← common commands (make help)
├── docker-compose.yml          ← orchestrates all four bots
├── .env.example                ← all secrets, prefixed per bot
├── .gitignore
│
├── bots/
│   ├── leocard/                ← python-telegram-bot + OCR + Google APIs
│   ├── newbie/                 ← stateless info bot
│   ├── profcom/                ← aiogram + Gemini + python-docx
│   └── tickets/                ← aiogram + Sheets (service account)
│
├── shared/
│   ├── __init__.py
│   └── logging_config.py       ← common logging — has a TODO for you
│
├── data/                       ← host-side persistent state (git-ignored)
│   ├── leocard/
│   │   ├── credentials.json    ← Google OAuth client (put here manually)
│   │   ├── token.json          ← Google OAuth refresh token (auto-refreshed)
│   │   └── bot_persistence/    ← PicklePersistence state
│   ├── profcom/
│   │   ├── credentials.json
│   │   ├── token.json
│   │   ├── generated_petitions/
│   │   └── notification_chats.json
│   └── tickets/
│       └── service_account.json  ← Google service account JSON key
│
├── .github/workflows/
│   └── deploy.yml              ← auto-deploy on push to main (self-hosted runner)
│
├── docs/
│   └── DEPLOY.md               ← EC2 secrets layout, runner setup, credential generation
│
└── infrastructure/
    └── terraform/              ← VPC + EC2 + SG (SSH-only inbound)
```

## Quick start (local / development)

```bash
# 1. Create data dirs, .env, placeholder credential files
make init

# 2. Fill in all secrets in .env
$EDITOR .env

# 3. Drop real Google credential files into data/<bot>/
#    (see docs/DEPLOY.md section 4 for how to generate them)
cp ~/Downloads/leocard_credentials.json data/leocard/credentials.json
cp ~/Downloads/leocard_token.json       data/leocard/token.json
# ... same for profcom ...
cp ~/Downloads/tickets_sa.json          data/tickets/service_account.json

# 4. Implement the TODOs (there are two — see below)
$EDITOR shared/logging_config.py
$EDITOR bots/tickets/config.py

# 5. Verify everything is in place
make doctor

# 6. Build and launch
make up
make logs                    # all four bots combined
make logs-tickets            # just one
```

## Things you need to fill in

Two files contain deliberate `TODO` blocks — each with ~5–10 lines of code
to write. They're left for you because the right answer depends on how
you actually plan to run things, and no amount of defaulting is going to
guess correctly:

1. **`shared/logging_config.py`** — choose a logging strategy: stdout-only
   (12-factor), stdout + rotating file, or JSON logs. Trade-offs are
   spelled out in comments inside the file.

2. **`bots/tickets/config.py`** → `payment_instructions(qty, cfg)` — decide
   how buyers actually pay. Monojar URL with amount query string? Plain
   card number? Static jar with manual amount? Bulk discount at qty ≥ 5?
   Comments in the file walk through the options.

Until you implement them, the relevant bot will raise `NotImplementedError`
on startup. This is intentional — I'd rather fail loudly than guess.

## Google credentials policy

The monorepo intentionally does **not** store Google OAuth tokens in
environment variables. Instead:

- **Leocard / Profcom** use OAuth 2.0 user credentials. Put real
  `credentials.json` + `token.json` files into `data/<bot>/` — they're
  bind-mounted into the containers. The `google-auth` library refreshes
  the access token automatically and writes updates back to the same
  file through the bind-mount, so refreshes persist across container
  restarts with zero code changes.

- **Tickets** uses a Service Account — long-lived JSON key that doesn't
  expire. Generate once, drop into `data/tickets/service_account.json`,
  share the target Sheet with the service account's email, done.

Step-by-step instructions for generating these files are in
`docs/DEPLOY.md` section 4.

## How secrets are organised

`.env` stores prefixed names so they don't collide:

```
LEOCARD_TELEGRAM_BOT_TOKEN=...
NEWBIE_BOT_TOKEN=...
PROFCOM_TELEGRAM_BOT_TOKEN=...
TICKETS_TELEGRAM_BOT_TOKEN=...
```

`docker-compose.yml` then re-maps each prefixed var to the plain name the
bot's existing code expects. **You do not need to edit any bot's Python
code to make it monorepo-aware.** The bots stay exactly as they were —
only the way they're launched changes.

## Deploying to AWS

Two-phase deploy:

1. **Provision infra once with Terraform** (see
   `infrastructure/terraform/README.md`). Creates a closed VPC, a
   t3.micro EC2 with an Elastic IP, and a security group whose only
   inbound rule is SSH from your IP.

2. **Bootstrap the box and install a self-hosted GitHub Actions runner**
   (see `docs/DEPLOY.md`). This is a one-time manual step: lay out the
   secret files in `/etc/telegram-bots/`, install the runner, wire it up
   with a registration token from GitHub.

After that, **`git push origin main`** auto-deploys. The runner picks up
the job, checks out the commit, symlinks persistent secrets and state into
the workspace, rebuilds affected images, restarts containers, prunes
dangling images, and smoke-tests that every bot is in `running` state.

## Why four different... wait, three frameworks

`python-telegram-bot` × 2 (leocard, newbie), `aiogram` × 2 (profcom,
tickets). I deliberately did **not** unify them onto a single framework —
both are mature, the bots work as-is, and rewriting thousands of lines of
FSM/handler code just to achieve stylistic uniformity is exactly the kind
of unforced-error refactor that eats weeks and introduces bugs. A monorepo
unifies _operations_, not necessarily implementations.

## Original projects

The three original repos still live untouched next to this monorepo at:

- `../Leocard_bot/`
- `../newbie_bot/`
- `../Profcom_bot/`

Once you've verified the monorepo works end-to-end on the EC2 box, you can
delete them.
