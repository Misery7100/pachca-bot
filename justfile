default:
    @just --list

install:
    uv sync

lint:
    uv run ruff check src/ tests/

lint-fix:
    uv run ruff check --fix src/ tests/

format:
    uv run ruff format src/ tests/

test *args:
    uv run pytest tests/ -v {{args}}

run:
    uv run python -m pachca_bot

docker-build tag="pachca-bot:latest":
    docker build -t {{tag}} .

docker-run tag="pachca-bot:latest":
    docker run --rm -p 8000:8000 \
        -e PACHCA_ACCESS_TOKEN \
        -e PACHCA_CHAT_ID \
        -e GITHUB_WEBHOOK_SECRET \
        -e GENERIC_WEBHOOK_SECRET \
        {{tag}}

check: lint test
