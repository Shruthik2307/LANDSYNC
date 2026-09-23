#!/usr/bin/env bash
# LANDSYNC deployment-architecture guard (CI gate 1).
#
# Fails if prohibited deployment references appear in RUNTIME/application
# files. Documentation (README, *.md, openapi.yaml, .env.example, this repo's
# own guard scripts) is deliberately exempt — we want docs that explain WHY
# the split deployment is obsolete, not runtime code that depends on it.
#
# Scope notes:
#   - src/ backend/ engine/  = shipped runtime code (strict rules apply)
#   - vite.config.js, server/ = local dev tooling (Vite dev proxy and the
#     dev mock server legitimately bind/call localhost) — exempt from the
#     localhost rule, still scanned for external deployment hostnames.
#
# Prohibited:
#   - split-deploy config files: vercel.json / render.yaml / netlify.toml / railway.json
#   - *.vercel.app / *.onrender.com / *.netlify.app hostnames in runtime code
#   - hardcoded localhost:8000 / 127.0.0.1:8000 API URLs in shipped runtime code
#   - a remote VITE_API_BASE_URL baked into env files committed to the repo
set -uo pipefail
fail=0

echo "== split-deploy config files =="
for f in vercel.json render.yaml netlify.toml railway.json; do
  if [ -e "$f" ]; then
    echo "FAIL: split-deploy config file present: $f"
    fail=1
  fi
done

echo "== external deployment hostnames in runtime code (comment-only lines exempt) =="
# Comment-only lines are exempt (docs-in-code explaining the old bug are good);
# hostnames inside actual string literals / code lines still fail.
TMP_HITS="$(mktemp)"
grep -rniE 'vercel\.app|onrender\.com|netlify\.app' \
     src backend engine server vite.config.js Dockerfile package.json index.html 2>/dev/null \
     --include='*.js' --include='*.jsx' --include='*.py' --include='*.json' \
     --include='*.html' --include='*.mjs' --include='Dockerfile' > "$TMP_HITS" || true
# Drop comment-only matches: "path:line:// …", "path:line:# …", "path:line:/* …", "path:line:* …"
sed -i -E '/:[0-9]+:[[:space:]]*(\/\/|#|\/\*|\*)/d' "$TMP_HITS"
if [ -s "$TMP_HITS" ]; then
  cat "$TMP_HITS"
  echo "FAIL: hardcoded external deployment hostname in runtime code (see matches above)"
  fail=1
fi
rm -f "$TMP_HITS"

echo "== localhost API URLs in shipped runtime code =="
LOCALHOST_HITS="$(mktemp)"
grep -rniE '(localhost|127\.0\.0\.1):8000' src backend engine 2>/dev/null \
     --include='*.js' --include='*.jsx' --include='*.py' > "$LOCALHOST_HITS" || true
sed -i -E '/:[0-9]+:[[:space:]]*(\/\/|#|\/\*|\*)/d' "$LOCALHOST_HITS"
if [ -s "$LOCALHOST_HITS" ]; then
  cat "$LOCALHOST_HITS"
  echo "FAIL: hardcoded localhost API URL in shipped runtime code (dev must use the Vite proxy or an empty VITE_API_BASE_URL)"
  fail=1
fi
rm -f "$LOCALHOST_HITS"

echo "== env files must not pin a remote API host =="
for envf in .env .env.production .env.local; do
  if [ -f "$envf" ]; then
    if grep -E '^VITE_API_BASE_URL=https?://' "$envf" >/dev/null 2>&1; then
      echo "FAIL: $envf pins VITE_API_BASE_URL to a remote host — production must be same-origin"
      fail=1
    fi
  fi
done

if [ "$fail" -ne 0 ]; then
  echo ""
  echo "Deployment hygiene check FAILED. Production is the single-service"
  echo "Railway deployment; API calls must be same-origin ('/api/...')."
  echo "See README 'Deployment' section. Documentation mentions are fine —"
  echo "this gate only scans runtime/application files."
  exit 1
fi
echo "Deployment hygiene: OK"
