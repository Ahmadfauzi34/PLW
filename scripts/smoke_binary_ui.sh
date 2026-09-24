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

mkdir -p "$TMP/home" "$TMP/run" "$TMP/project/src/app"
cp "$BIN" "$TMP/run/plw"
chmod +x "$TMP/run/plw"

cat > "$TMP/project/src/app/modal.service.ts" <<'EOF'
export class ModalService { open=false; }
EOF

cat > "$TMP/project/src/app/app.component.ts" <<'EOF'
import { Component } from '@angular/core';
import { ModalService } from './modal.service';
@Component({selector:'app-root',templateUrl:'./app.component.html',styleUrls:['./app.component.scss']})
export class AppComponent { constructor(public modal: ModalService) {} }
EOF

cat > "$TMP/project/src/app/app.component.html" <<'EOF'
<main><button id="pay">Pay</button><footer id="footer">Footer</footer></main>
EOF

cat > "$TMP/project/src/app/app.component.scss" <<'EOF'
button{} footer{}
EOF

cat > "$TMP/project/page.html" <<'EOF'
<!doctype html><html><head><style>
html,body{margin:0;width:100%;height:100%;overflow:hidden}
app-root{display:block;position:relative;width:390px;height:844px}
#pay{position:absolute;left:24px;top:780px;width:342px;height:48px;z-index:2}
#footer{position:absolute;left:0;top:770px;width:390px;height:74px;z-index:4;background:#ddd}
</style></head><body><app-root><button id="pay">Pay</button><footer id="footer">Footer</footer></app-root></body></html>
EOF

cd "$TMP/run"
export HOME="$TMP/home"
export XDG_STATE_HOME="$TMP/home/state"
export XDG_CACHE_HOME="$TMP/home/cache"

./plw angular-anchors "$TMP/project" --json > "$TMP/ownership.json"

python - "$TMP" <<'PY'
import json
from pathlib import Path
import sys

root = Path(sys.argv[1])
ownership = json.loads((root / "ownership.json").read_text())
scenario = {
    "route": "/checkout",
    "viewport": [390, 844],
    "ui_state": "modal-open",
    "data_fixture": "anonymous",
}

def snapshot(revision, pay_y):
    return {
        "schema_version": "geometry-snapshot-v1",
        "scenario": {"code_revision": revision, **scenario},
        "static_context": {
            "graph_content_signature": ownership["graph_content_signature"],
            "angular_ownership_digest": ownership["ownership_digest"],
        },
        "capture": {"source": "standalone-binary-ci"},
        "nodes": [
            {
                "ui_id": "id:root",
                "tag_name": "app-root",
                "bbox": [0, 0, 390, 844],
                "visible": True,
                "z_index": 0,
                "owner": {"component_selector": "app-root"},
            },
            {
                "ui_id": "id:pay",
                "tag_name": "button",
                "parent_ui_id": "id:root",
                "bbox": [24, pay_y, 342, 48],
                "visible": True,
                "z_index": 2,
                "owner": {"component_selector": "app-root"},
            },
            {
                "ui_id": "id:footer",
                "tag_name": "footer",
                "parent_ui_id": "id:root",
                "bbox": [0, 770, 390, 74],
                "visible": True,
                "z_index": 4,
                "owner": {"component_selector": "app-root"},
            },
        ],
    }

(root / "baseline.json").write_text(json.dumps(snapshot("r1", 700)))
(root / "candidate.json").write_text(json.dumps(snapshot("r2", 780)))
PY

./plw ui map "$TMP/candidate.json" "$TMP/project" --json > "$TMP/ui-map.json"
./plw ui diagnose "$TMP/candidate.json" --baseline "$TMP/baseline.json" --root "$TMP/project" --json > "$TMP/diagnosis.json"

python - "$TMP" <<'PY'
import json
from pathlib import Path
import sys

root = Path(sys.argv[1])
ui_map = json.loads((root / "ui-map.json").read_text())
diagnosis = json.loads((root / "diagnosis.json").read_text())

overlaps = [
    issue for issue in ui_map.get("issues", [])
    if issue.get("kind") == "OVERLAP" and issue.get("severity") == "CRITICAL"
]
if not overlaps:
    raise SystemExit("binary UI map did not detect expected critical overlap")
if diagnosis.get("summary", {}).get("bug_candidate_count", 0) < 1:
    raise SystemExit("binary UI diagnosis did not produce a bug candidate")

print("STANDALONE_UI_STATIC_SMOKE: PASS")
PY

browser_args=()
if [[ -n "${PLW_BROWSER_EXECUTABLE:-}" ]]; then
  browser_args=(--browser "$PLW_BROWSER_EXECUTABLE")
fi

if [[ -n "${PLW_BROWSER_EXECUTABLE:-}" ]] || command -v chromium >/dev/null 2>&1 ||    command -v chromium-browser >/dev/null 2>&1 ||    command -v google-chrome >/dev/null 2>&1 ||    command -v google-chrome-stable >/dev/null 2>&1; then
  for attempt in 1 2 3; do
    ./plw ui reproduce "$TMP/diagnosis.json" \
      --root "$TMP/project" \
      --html-file "$TMP/project/page.html" \
      "${browser_args[@]}" \
      --json > "$TMP/reproduction.json"

    classification="$(python - "$TMP/reproduction.json" <<'PY'
import json
from pathlib import Path
import sys

result = json.loads(Path(sys.argv[1]).read_text())
state = result.get("reproduction_state")
reason = result.get("reason")
error = str(result.get("error") or "")

if state == "REPRODUCED":
    print("REPRODUCED")
elif (
    state == "UNRESOLVED"
    and reason == "browser_execution_unresolved"
    and "timed out" in error.lower()
):
    print("RETRYABLE_CDP_STARTUP")
else:
    print("HARD_FAILURE")
PY
)"

    if [[ "$classification" == "REPRODUCED" ]]; then
      break
    fi
    if [[ "$classification" != "RETRYABLE_CDP_STARTUP" ]]; then
      break
    fi
    if [[ "$attempt" -lt 3 ]]; then
      echo "Chromium CDP startup timed out on attempt $attempt; retrying." >&2
      sleep 2
    fi
  done

  python - "$TMP/reproduction.json" <<'PY'
import json
from pathlib import Path
import sys

result = json.loads(Path(sys.argv[1]).read_text())
if result.get("reproduction_state") != "REPRODUCED":
    raise SystemExit(
        "expected REPRODUCED, "
        f"got {result.get('reproduction_state')}; "
        f"reason={result.get('reason')}; error={result.get('error')}"
    )
if result.get("execution", {}).get("browser_executed_by_plw") is not True:
    raise SystemExit("browser was not executed by PLW")
if result.get("authority", {}).get("root_cause_proven") is not False:
    raise SystemExit("runtime reproduction incorrectly claimed root-cause proof")
print("STANDALONE_UI_BROWSER_SMOKE: PASS")
PY
else
  if [[ "${PLW_REQUIRE_BROWSER:-0}" == "1" ]]; then
    echo "STANDALONE_UI_BROWSER_SMOKE: FAIL browser_required_but_not_found" >&2
    exit 1
  fi
  echo "STANDALONE_UI_BROWSER_SMOKE: SKIP browser_not_found"
fi

python - "$TMP/project" <<'PY'
from pathlib import Path
import sys

project = Path(sys.argv[1])
for forbidden in ("data/runtime", "data/codebase/cache"):
    if (project / forbidden).exists():
        raise SystemExit(f"target repository polluted by PLW runtime state: {forbidden}")
print("STANDALONE_UI_TARGET_CLEAN: PASS")
PY
