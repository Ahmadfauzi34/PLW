#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BIN="${1:-$ROOT/artifacts/plw-linux-x86_64}"

if [[ ! -x "$BIN" ]]; then
  echo "binary not executable: $BIN" >&2
  exit 2
fi

TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT

mkdir -p "$TMP/empty-home" "$TMP/fixture/src" "$TMP/run"
cat > "$TMP/fixture/src/main.ts" <<'EOF'
import { value } from "./value";
console.log(value);
EOF
cat > "$TMP/fixture/src/value.ts" <<'EOF'
export const value = 1;
EOF

cp "$BIN" "$TMP/run/plw"
cd "$TMP/run"
export HOME="$TMP/empty-home"
export XDG_STATE_HOME="$TMP/empty-home/state"
export XDG_CACHE_HOME="$TMP/empty-home/cache"

./plw help >/dev/null
./plw topology "$TMP/fixture" --json > "$TMP/topology.json"
./plw impact src/value.ts "$TMP/fixture" --json > "$TMP/impact.json"

python - "$TMP/topology.json" "$TMP/impact.json" "$TMP/fixture" <<'PY'
import json
from pathlib import Path
import sys
topology = json.loads(Path(sys.argv[1]).read_text())
impact = json.loads(Path(sys.argv[2]).read_text())
fixture = Path(sys.argv[3])
if topology.get('error'): raise SystemExit(f"topology failed: {topology['error']}")
if impact.get('error'): raise SystemExit(f"impact failed: {impact['error']}")
for forbidden in ('data/runtime', 'data/codebase/cache'):
    if (fixture / forbidden).exists():
        raise SystemExit(f'target repository polluted by PLW runtime state: {forbidden}')
print('STANDALONE_BINARY_SMOKE: PASS')
PY
