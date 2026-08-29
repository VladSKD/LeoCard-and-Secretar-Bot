.PHONY: help init doctor up down restart build rebuild logs ps \
        logs-leocard logs-newbie logs-profcom \
        shell-leocard shell-newbie shell-profcom \
        tf-init tf-plan tf-apply tf-destroy

# Default target — show available commands
help:
	@echo "Telegram bots monorepo — available targets:"
	@echo ""
	@echo "  make init             Create data dirs, .env, placeholder credential files"
	@echo "  make doctor           Verify that secret files are in place before 'make up'"
	@echo "  make up               Start the three main bots (leocard, newbie, profcom)"
	@echo "  make down             Stop all bots"
	@echo "  make restart          Restart all bots"
	@echo "  make build            Build images without starting"
	@echo "  make rebuild          Force rebuild (no cache) and restart"
	@echo "  make logs             Tail logs from all bots"
	@echo "  make logs-<bot>       Tail logs for one bot (leocard|newbie|profcom)"
	@echo "  make ps               List container status"
	@echo "  make shell-<bot>      Open a shell inside a running container"
	@echo ""
	@echo "  make tf-init          terraform init"
	@echo "  make tf-plan          terraform plan"
	@echo "  make tf-apply         terraform apply"
	@echo "  make tf-destroy       terraform destroy"

init:
	@mkdir -p data/leocard/bot_persistence data/profcom/generated_petitions data/shared
	@[ -f data/shared/notification_chats.json ] || echo '{"chat_ids": []}' > data/shared/notification_chats.json
	@touch data/leocard/credentials.json data/leocard/token.json
	@touch data/profcom/credentials.json data/profcom/token.json
	@chmod 600 data/leocard/token.json data/profcom/token.json \
		data/leocard/credentials.json data/profcom/credentials.json 2>/dev/null || true
	@[ -f .env ] || cp .env.example .env
	@echo ""
	@echo "✓ data/ created, .env ready."
	@echo "  Next: edit .env, drop real Google credential files into data/<bot>/,"
	@echo "  then run 'make doctor' to verify, then 'make up'."

doctor:
	@set -e; \
	fail=0; \
	check_nonempty() { \
		if [ ! -s "$$1" ]; then \
			echo "  ✗ $$1 is missing or empty — $$2"; \
			fail=1; \
		else \
			echo "  ✓ $$1"; \
		fi; \
	}; \
	echo "Checking secrets and credential files..."; \
	check_nonempty .env "copy .env.example and fill it in"; \
	check_nonempty data/leocard/credentials.json "OAuth client JSON (see docs/DEPLOY.md)"; \
	check_nonempty data/leocard/token.json "OAuth refresh token JSON (see docs/DEPLOY.md)"; \
	check_nonempty data/profcom/credentials.json "OAuth client JSON"; \
	check_nonempty data/profcom/token.json "OAuth refresh token JSON"; \
	if [ $$fail -eq 0 ]; then \
		echo "All checks passed. You can 'make up'."; \
	else \
		echo ""; \
		echo "Fix the items above before running 'make up'."; \
		exit 1; \
	fi

up:
	docker compose up -d

down:
	docker compose down

restart:
	docker compose restart

build:
	docker compose build

rebuild:
	docker compose build --no-cache
	docker compose up -d

logs:
	docker compose logs -f --tail=100

logs-leocard:
	docker compose logs -f --tail=100 leocard

logs-newbie:
	docker compose logs -f --tail=100 newbie

logs-profcom:
	docker compose logs -f --tail=100 profcom

ps:
	docker compose ps

shell-leocard:
	docker compose exec leocard /bin/bash

shell-newbie:
	docker compose exec newbie /bin/bash

shell-profcom:
	docker compose exec profcom /bin/bash

# ─── Terraform ──────────────────────────────────────────────────────────────
TF_DIR := infrastructure/terraform

tf-init:
	cd $(TF_DIR) && terraform init

tf-plan:
	cd $(TF_DIR) && terraform plan

tf-apply:
	cd $(TF_DIR) && terraform apply

tf-destroy:
	cd $(TF_DIR) && terraform destroy
