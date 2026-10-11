#!/bin/sh
# Прогон pytest на Linux: Docker python:3.12-slim + uv. Репо монтируется только на чтение и копируется
# без saves/, .venv, .git, .env, mutants/ и кэшей; ключи API в контейнер не передаются.
# Нужен запущенный Docker (демон). Запуск: make linux-check
set -eu
root=$(cd "$(dirname "$0")/.." && pwd)
docker run --rm -v "$root":/src:ro python:3.12-slim sh -c '
set -eu
mkdir /work
tar -C /src --exclude=./saves --exclude=./.venv --exclude=./.git --exclude="./.env*" \
    --exclude=./mutants --exclude=./dist --exclude=./.pytest_cache --exclude=./.ruff_cache \
    --exclude="__pycache__" --exclude=./.coverage -cf - . | tar -C /work -xf -
cd /work
pip install -q uv==0.12.22
export UV_LINK_MODE=copy
uv sync --locked -q
uv run pytest -q
'
