#!/bin/bash
# Loads .env from project root and runs dbt with any arguments passed in.
# Usage from dbt_project/ folder:
#   ./dbt_run.sh debug
#   ./dbt_run.sh build

set -a
source "$(dirname "$0")/../.env"
set +a

source "$(dirname "$0")/../venv/bin/activate"

dbt "$@" --profiles-dir .
