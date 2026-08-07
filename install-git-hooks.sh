#!/usr/bin/env sh
# Configure this clone to use the versioned Git hooks in .githooks.
set -eu

project_root="$(git rev-parse --show-toplevel)"
cd "$project_root"
git config core.hooksPath .githooks

echo "Git hooks installed from $project_root/.githooks"
