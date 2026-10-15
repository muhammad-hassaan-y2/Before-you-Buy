SERVICES := api-gateway catalog-service inference-service vision-service geometry-service scene-service

.PHONY: up down logs build rebuild test lint install clean

up: ## run the full stack (add `PROFILE=gpu` to start vLLM)
	docker compose $(if $(PROFILE),--profile $(PROFILE),--profile none) up --build -d

down: ## stop the stack and remove containers
	docker compose down

clean: ## stop the stack and delete volumes (drops simulation data)
	docker compose down -v --remove-orphans

logs: ## tail all services
	docker compose logs -f --tail 100

build: ## build images without starting them
	docker compose build

rebuild: ## rebuild without cache
	docker compose build --no-cache

test: ## run each service test suite with host Poetry
	@for s in $(SERVICES); do \
		echo "== $$s"; \
		(cd services/$$s && poetry run pytest -q) || exit 1; \
	done

lint: ## ruff over all services with host Poetry
	@for s in $(SERVICES); do \
		(cd services/$$s && poetry run ruff check src tests) || exit 1; \
	done

install: ## poetry install locally in each service (needs Poetry on the host)
	(cd libs/byb-common && poetry install)
	@for s in $(SERVICES); do (cd services/$$s && poetry install); done
	(cd frontend && pnpm install)
