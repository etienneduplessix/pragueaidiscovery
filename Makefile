# File: Makefile

# Default .env file path
ENV_FILE=.env

# Compose command with env file
DC=docker compose --env-file $(ENV_FILE)

# Container names
WEB=web
N8N=n8n
DB=db

# Targets

.PHONY: up down restart logs build shell webshell dbshell n8nshell ps prune

## Start all containers
up:
	$(DC) up -d --build

## Stop all containers
down:
	$(DC) down

## Restart everything
restart:
	$(MAKE) down
	$(MAKE) up

## Show container logs
logs:
	$(DC) logs -f

## Rebuild services
build:
	$(DC) build

## Shell into the web (FastAPI) container
webshell:
	$(DC) exec $(WEB) bash

## Shell into the PostgreSQL container
dbshell:
	$(DC) exec $(DB) bash

## Shell into the n8n container
n8nshell:
	$(DC) exec $(N8N) bash

## Show running containers
ps:
	$(DC) ps

## Clean up unused Docker resources
prune:
	docker system prune -f
