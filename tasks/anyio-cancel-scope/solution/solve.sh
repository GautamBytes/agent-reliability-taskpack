#!/bin/sh
set -eu
repo=${1:-/app/repo}
solution_dir=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
if patch --dry-run --silent -f -R -d "$repo" -p1 < "$solution_dir/reference.patch" >/dev/null 2>&1; then
    printf '%s\n' 'Reference change is already applied.'
elif patch --dry-run --silent -f -N -d "$repo" -p1 < "$solution_dir/reference.patch" >/dev/null 2>&1; then
    patch --silent -f -N -d "$repo" -p1 < "$solution_dir/reference.patch"
else
    printf '%s\n' 'Reference patch does not apply to this source tree.' >&2
    exit 1
fi
