#!/usr/bin/env bash
# Assemble the static demo. The Python under dist/engine/ is copied, never
# edited, so the hosted page runs the same code as the desktop app.
set -euo pipefail

root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
out="$root/web/dist"

rm -rf "$out"
mkdir -p "$out/engine" "$out/datasets" "$out/fonts"

cp "$root"/web/*.html "$root"/web/*.css "$root"/web/*.js "$root"/web/*.svg "$root"/web/*.png "$out/"
cp "$root"/web/*.json "$out/"
cp "$root"/web/engine.py "$out/engine/"
for module in answer_format data_pipeline question_actions table_analysis; do
  cp "$root/src/$module.py" "$out/engine/"
done
cp "$root"/web/datasets/*.csv "$out/datasets/"
cp "$root"/web/fonts/*.woff2 "$out/fonts/"

echo "built $out"
