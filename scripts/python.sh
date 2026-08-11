#!/bin/sh

set -eu

script_dir=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
project_dir=$(CDPATH= cd -- "$script_dir/.." && pwd)
project_python="$project_dir/.venv/bin/python"

if [ -x "$project_python" ]; then
  exec "$project_python" "$@"
fi

exec python3 "$@"
