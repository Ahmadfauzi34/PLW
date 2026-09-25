#!/usr/bin/env bash
set -euo pipefail

BIN="$(realpath "${1:-artifacts/plw-linux-x86_64}")"
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT
mkdir -p "$TMP/project/src/app" "$TMP/run"

cat > "$TMP/project/src/app/header.component.ts" <<'EOF'
import { Component } from '@angular/core';
@Component({ selector: 'app-header', templateUrl: './header.component.html' })
export class HeaderComponent {}
EOF
cat > "$TMP/project/src/app/header.component.html" <<'EOF'
<nav><a routerLink="/login"><span>Sign in</span></a><a routerLink="/register">Sign up</a></nav>
EOF
cat > "$TMP/project/src/app/article.component.ts" <<'EOF'
import { Component } from '@angular/core';
@Component({ selector: 'app-article', template: `<a routerLink="/login">Sign in</a>` })
export class ArticleComponent {}
EOF
cat > "$TMP/project/angular.json" <<'EOF'
{"projects":{"example":{"architect":{"build":{"options":{"styles":["src/global.css"]}}}}}}
EOF

export HOME="$TMP/home" XDG_STATE_HOME="$TMP/state" XDG_CACHE_HOME="$TMP/cache"
cd "$TMP/run"
"$BIN" capability describe ui-static --json > "$TMP/capability.json"
"$BIN" skill show ui-static --json > "$TMP/skill.json"
"$BIN" ui static 'Sign in' "$TMP/project" --json > "$TMP/ambiguous.json"
"$BIN" ui static 'Sign in' "$TMP/project" --selector app-header --json > "$TMP/header.json"
"$BIN" ui-static 'Sign in' "$TMP/project" --selector app-article --json > "$TMP/inline.json"
"$BIN" ui static 'missing exact control' "$TMP/project" --json > "$TMP/missing.json"
"$BIN" ui static 'register' "$TMP/project" --selector app-header --json > "$TMP/attribute.json"
cat > "$TMP/project/src/app/broken.component.ts" <<'EOF'
import { Component } from '@angular/core';
@Component({ selector: 'app-broken', templateUrl: './missing.component.html' })
export class BrokenComponent {}
EOF
"$BIN" ui static 'Sign up' "$TMP/project" --json > "$TMP/unreadable.json"

python - "$TMP" "$BIN" <<'PY'
import hashlib
import json
from pathlib import Path
import subprocess
import sys

root, binary = Path(sys.argv[1]), sys.argv[2]
read = lambda name: json.loads((root / f"{name}.json").read_text())
assert read("capability")["known"] is True
assert read("skill")["known"] is True
assert read("ambiguous")["decision"]["status"] == "AMBIGUOUS"
assert read("ambiguous")["decision"]["selected"] is None
assert read("ambiguous")["decision"]["top_score_tie_count"] == 2
header = read("header")
assert header["decision"]["status"] == "RESOLVED"
selected = header["decision"]["selected"]
assert selected["component_class"] == "HeaderComponent"
assert selected["element"]["tag"] == "a"
assert selected["element"]["label"] == "Sign in"
assert selected["element"]["label_provenance"] == "NESTED_TEXT_IN_INTERACTIVE_CONTROL"
assert selected["match_evidence"]["label_terms"] == ["in", "sign"]
assert selected["match_evidence"]["label_phrase_in_query"] is True
assert all(row["element"]["tag"] not in {"nav", "span"} for row in header["candidates"])
assert any(row["element"]["label"] == "Sign up" and
           row["score"] < selected["score"] and
           row["match_evidence"]["label_phrase_in_query"] is False
           for row in header["candidates"])
assert selected["element"]["attributes"]["routerlink"] == "/login"
assert selected["template_line"] == 1
expected = "sha256:" + hashlib.sha256((root / "project/src/app/header.component.html").read_bytes()).hexdigest()
assert selected["template_sha256"] == expected
assert header["declared_global_styles"][0]["status"] == "UNAVAILABLE"
assert header["authority"]["geometry_observed"] is False
assert header["authority"]["overlap_proven"] is False
inline = read("inline")
assert inline["decision"]["status"] == "RESOLVED"
assert inline["decision"]["selected"]["template_proof"] == "EXACT_INLINE"
assert inline["decision"]["selected"]["template_line"] is None
assert read("missing")["decision"]["status"] == "UNRESOLVED"
attribute = read("attribute")["decision"]["selected"]
assert attribute["element"]["attributes"]["routerlink"] == "/register"
assert attribute["match_evidence"]["attribute_terms"] == {"routerlink": ["register"]}
unreadable = read("unreadable")
assert unreadable["decision"]["status"] == "AMBIGUOUS"
assert unreadable["decision"]["reason"] == "unresolved_templates_may_contain_candidate"
assert unreadable["unresolved_templates"]
bad = subprocess.run([binary, "ui", "static", "", str(root / "project"), "--json"],
                     text=True, capture_output=True)
assert bad.returncode == 2 and "invalid_static_ui_query" in bad.stderr
assert sorted(p.name for p in (root / "project/src/app").iterdir()) == [
    "article.component.ts", "broken.component.ts", "header.component.html", "header.component.ts"]
print("UI_STATIC_SMOKE: PASS ambiguity=retained template=exact inline=bound browser=unused")
PY
