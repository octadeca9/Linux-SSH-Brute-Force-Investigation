#!/usr/bin/env bash
# Generate GROUND_TRUTH_B64 for env-only platforms (no file mounts).
#
# Emits the base64 of config/ground_truth.yaml as a SINGLE line (no wrapping),
# which the app decodes at runtime via loaders.load_ground_truth(). This keeps
# the answer key out of the image while still letting the validator score.
#
# Usage:
#   scripts/gen-ground-truth-b64.sh                 # print the raw b64 value
#   scripts/gen-ground-truth-b64.sh --env           # print GROUND_TRUTH_B64=<value>
#   scripts/gen-ground-truth-b64.sh path/to/gt.yaml # use a different source file
#
# Example (set it in your current shell):
#   export "$(scripts/gen-ground-truth-b64.sh --env)"
set -euo pipefail

cd "$(dirname "$0")/.."

ENV_FORMAT=0
SRC="config/ground_truth.yaml"
for arg in "$@"; do
  case "$arg" in
    --env) ENV_FORMAT=1 ;;
    -h|--help) grep '^#' "$0" | sed 's/^# \{0,1\}//'; exit 0 ;;
    *) SRC="$arg" ;;
  esac
done

[ -f "$SRC" ] || { echo "error: source file not found: $SRC" >&2; exit 1; }

# Validate it is parseable YAML before encoding, if python is available.
if command -v python3 >/dev/null 2>&1; then
  python3 - "$SRC" <<'PY' || { echo "error: $SRC is not valid YAML" >&2; exit 1; }
import sys, yaml
with open(sys.argv[1]) as fh:
    data = yaml.safe_load(fh)
assert isinstance(data, dict) and "tasks" in data, "missing 'tasks' key"
PY
fi

# base64 with no line wrapping (portable across macOS/BSD and GNU).
B64="$(base64 < "$SRC" | tr -d '\n')"

# Round-trip check: decode must byte-match the source.
if ! printf '%s' "$B64" | base64 --decode | cmp -s - "$SRC"; then
  echo "error: base64 round-trip did not match source" >&2
  exit 1
fi

if [ "$ENV_FORMAT" -eq 1 ]; then
  printf 'GROUND_TRUTH_B64=%s\n' "$B64"
else
  printf '%s\n' "$B64"
fi
