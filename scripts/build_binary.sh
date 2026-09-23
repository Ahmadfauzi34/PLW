#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

python scripts/check_binary_safety.py

if [[ ! -f plw_cli.py ]]; then
  echo "plw_cli.py is missing; import the clean runtime source before building." >&2
  exit 2
fi

python -m pip install --upgrade pip
python -m pip install "pyinstaller>=6.10,<7"

rm -rf build dist
rm -f plw.spec

ARGS=(--noconfirm --clean --onefile --name plw --paths "$ROOT")
if [[ -d skills ]]; then
  ARGS+=(--add-data "skills:skills")
fi
if [[ -f VERSION ]]; then
  ARGS+=(--add-data "VERSION:.")
fi

python -m PyInstaller "${ARGS[@]}" plw_cli.py

mkdir -p artifacts
cp dist/plw artifacts/plw-linux-x86_64
chmod +x artifacts/plw-linux-x86_64
(cd artifacts && sha256sum plw-linux-x86_64 | tee plw-linux-x86_64.sha256)
