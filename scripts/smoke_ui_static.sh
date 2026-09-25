#!/usr/bin/env bash
set -euo pipefail

BIN="$(realpath "${1:-artifacts/plw-linux-x86_64}")"
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT
mkdir -p "$TMP/project/src/app" "$TMP/run"

cat > "$TMP/project/src/app/header.component.ts" <<'EOF'
import { Component } from '@angular/core';
@Component({ selector: 'app-header', templateUrl: './header.component.html', styleUrls: ['./header.component.css'] })
export class HeaderComponent {}
EOF
cat > "$TMP/project/src/app/header.component.html" <<'EOF'
<nav><a class="nav-link" routerLink="/login"><span>Sign in</span></a><a routerLink="/register">Sign up</a></nav>
EOF
cat > "$TMP/project/src/app/header.component.css" <<'EOF'
.nav-link { cursor: pointer; }
EOF
cat > "$TMP/project/src/app/article.component.ts" <<'EOF'
import { Component } from '@angular/core';
@Component({ selector: 'app-article', template: `<a routerLink="/login">Sign in</a>`, styles: [`a { color: red; }`] })
export class ArticleComponent {}
EOF
cat > "$TMP/project/src/app/conditions.component.ts" <<'EOF'
import { Component } from '@angular/core';
@Component({ selector: 'app-conditions', templateUrl: './conditions.component.html' })
export class ConditionsComponent {}
EOF
cat > "$TMP/project/src/app/conditions.component.html" <<'EOF'
@if (authState$ | async; as state) {
  @if (state === 'guest') {
    <button [hidden]="isLoading">Conditional action</button>
  } @else if (state === 'admin') {
    <a routerLink="/admin">Admin area</a>
  } @else {
    @for (item of items; track item.id) {
      <a routerLink="/details">Saved item</a>
    } @empty {
      <span>Nothing saved</span>
    }
  }
}
EOF
cat > "$TMP/project/src/app/unsupported.component.ts" <<'EOF'
import { Component } from '@angular/core';
@Component({ selector: 'app-unsupported', template: `@switch (mode) { @case ('x') { <a>Unknown control</a> } }` })
export class UnsupportedComponent {}
EOF
cat > "$TMP/project/src/app/malformed.component.ts" <<'EOF'
import { Component } from '@angular/core';
@Component({ selector: 'app-malformed', template: `@if (ready) { <a>Broken branch</a>` })
export class MalformedComponent {}
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
"$BIN" ui static 'nonexistent widget zzz' "$TMP/project" --json > "$TMP/missing.json"
"$BIN" ui static 'register' "$TMP/project" --selector app-header --json > "$TMP/attribute.json"
"$BIN" ui static 'Conditional action' "$TMP/project" --selector app-conditions --json > "$TMP/conditional.json"
"$BIN" ui static 'Saved item' "$TMP/project" --selector app-conditions --json > "$TMP/for.json"
"$BIN" ui static 'Admin area' "$TMP/project" --selector app-conditions --json > "$TMP/else-if.json"
"$BIN" ui static 'Nothing saved' "$TMP/project" --selector app-conditions --json > "$TMP/empty.json"
"$BIN" ui static 'Unknown control' "$TMP/project" --selector app-unsupported --json > "$TMP/unsupported.json"
"$BIN" ui static 'Broken branch' "$TMP/project" --selector app-malformed --json > "$TMP/malformed.json"
"$BIN" ui static 'authState' "$TMP/project" --selector app-conditions --json > "$TMP/control-syntax.json"
cat > "$TMP/project/src/app/broken.component.ts" <<'EOF'
import { Component } from '@angular/core';
@Component({ selector: 'app-broken', templateUrl: './missing.component.html' })
export class BrokenComponent {}
EOF
"$BIN" ui static 'Sign up' "$TMP/project" --json > "$TMP/unreadable.json"
cat > "$TMP/project/src/global.css" <<'EOF'
/* global style */
.nav-link { color: navy; }
@media (max-width: 600px) {
  .nav-link { display: none; }
  .shell .nav-link:hover { opacity: .5; }
}
EOF
"$BIN" ui static 'Sign in' "$TMP/project" --selector app-header --json > "$TMP/with-global-css.json"
"$BIN" ui static 'Sign in' "$TMP/project" --selector app-article --json > "$TMP/with-inline-css.json"
cat >> "$TMP/project/src/global.css" <<'EOF'
@import url('other.css');
EOF
"$BIN" ui static 'Sign in' "$TMP/project" --selector app-header --json > "$TMP/with-import.json"

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
style = selected["style_reference"]
assert style["status"] == "UNKNOWN" and "STYLESHEET_UNAVAILABLE" in style["issues"]
assert style["stylesheets"][0]["status"] == "EXACT"
assert style["candidate_rules"][0]["selector"] == ".nav-link"
assert style["candidate_rules"][0]["declarations"][0]["property"] == "cursor"
assert style["cascade_proven"] is False and style["geometry_observed"] is False
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
conditional = read("conditional")["decision"]["selected"]
flow = conditional["template_condition"]
assert flow["status"] == "CONDITIONAL_SOURCE"
assert [(b["kind"], b["source_location"]["line"]) for b in flow["angular_blocks"]] == [
    ("IF", 1), ("IF", 2)]
assert flow["structural_guards"][0]["kind"] == "[hidden]"
assert flow["active_branch_proven"] is False and flow["route_activation_proven"] is False
assert conditional["render_condition"] == "UNPROVEN"
assert [b["kind"] for b in read("for")["decision"]["selected"]["template_condition"]["angular_blocks"]] == [
    "IF", "ELSE", "FOR"]
assert [b["kind"] for b in read("else-if")["decision"]["selected"]["template_condition"]["angular_blocks"]] == [
    "IF", "ELSE_IF"]
assert [b["kind"] for b in read("empty")["decision"]["selected"]["template_condition"]["angular_blocks"]] == [
    "IF", "ELSE", "EMPTY"]
assert read("unsupported")["decision"]["selected"]["template_condition"]["status"] == "UNRESOLVED_CONTROL_FLOW"
malformed = read("malformed")["decision"]["selected"]["template_condition"]
assert malformed["status"] == "UNRESOLVED_CONTROL_FLOW"
assert "UNCLOSED_CONTROL_BLOCK" in malformed["parse_issues"]
assert read("control-syntax")["decision"]["status"] == "UNRESOLVED"
unreadable = read("unreadable")
assert unreadable["decision"]["status"] == "AMBIGUOUS"
assert unreadable["decision"]["reason"] == "unresolved_templates_may_contain_candidate"
assert unreadable["unresolved_templates"]
with_css = read("with-global-css")["decision"]["selected"]["style_reference"]
assert with_css["status"] == "BOUNDED_SOURCE" and not with_css["issues"]
assert len(with_css["candidate_rules"]) == 4
assert [r["selector_relation"] for r in with_css["candidate_rules"]] == [
    "LOCAL_COMPOUND_MATCH", "LOCAL_COMPOUND_MATCH", "LOCAL_COMPOUND_MATCH", "POSSIBLE_CONTEXT"]
assert [r["contexts"] for r in with_css["candidate_rules"]] == [
    [], [], ["@media (max-width: 600px)"], ["@media (max-width: 600px)"]]
assert with_css["media_active_proven"] is False and with_css["computed_style_observed"] is False
original_css = (root / "project/src/global.css").read_bytes().split(b"@import", 1)[0]
assert with_css["stylesheets"][1]["sha256"] == "sha256:" + hashlib.sha256(original_css).hexdigest()
assert with_css["stylesheets"][1]["config_sha256"] == "sha256:" + hashlib.sha256(
    (root / "project/angular.json").read_bytes()).hexdigest()
inline_css = read("with-inline-css")["decision"]["selected"]["style_reference"]
assert inline_css["status"] == "BOUNDED_SOURCE"
assert inline_css["candidate_rules"][0]["scope"] == "component"
assert inline_css["candidate_rules"][0]["declarations"][0]["value"] == "red"
assert inline_css["candidate_rules"][0]["line_basis"] == "INLINE_CSS_LITERAL"
assert inline_css["candidate_rules"][0]["declaration_line"] == 2
with_import = read("with-import")["decision"]["selected"]["style_reference"]
assert with_import["status"] == "UNKNOWN" and "UNRESOLVED_IMPORT" in with_import["issues"]
assert with_import["candidate_rules"]
bad = subprocess.run([binary, "ui", "static", "", str(root / "project"), "--json"],
                     text=True, capture_output=True)
assert bad.returncode == 2 and "invalid_static_ui_query" in bad.stderr
assert sorted(p.name for p in (root / "project/src/app").iterdir()) == [
    "article.component.ts", "broken.component.ts", "conditions.component.html", "conditions.component.ts",
    "header.component.css", "header.component.html", "header.component.ts", "malformed.component.ts", "unsupported.component.ts"]
print("UI_STATIC_SMOKE: PASS ambiguity=retained conditions=source-only css=bounded browser=unused")
PY
