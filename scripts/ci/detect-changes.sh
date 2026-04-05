#!/usr/bin/env bash
# Detect package changes since last tag and compute next versions.
# Called from publish.yaml — outputs are written to $GITHUB_OUTPUT.
set -euo pipefail

TARGET="${1:-auto}"
BUMP="${2:-patch}"

compute_version() {
  local prefix="$1" bump="$2"
  local last_tag
  last_tag=$(git tag -l "${prefix}/v*" | sort -V | tail -1)
  if [ -z "$last_tag" ]; then
    echo "0.1.0"
    return
  fi
  local current major minor patch
  current="${last_tag#"${prefix}/v"}"
  IFS='.' read -r major minor patch <<< "$current"
  case "$bump" in
    major) echo "$((major + 1)).0.0" ;;
    minor) echo "${major}.$((minor + 1)).0" ;;
    *)     echo "${major}.${minor}.$((patch + 1))" ;;
  esac
}

has_changes() {
  local prefix="$1"
  shift
  local last_tag
  last_tag=$(git tag -l "${prefix}/v*" | sort -V | tail -1)
  if [ -z "$last_tag" ]; then
    return 0
  fi
  ! git diff --quiet "$last_tag" -- "$@"
}

GAMEDATA=false
API=false
DEVDATA=false

if [ "$TARGET" = "auto" ]; then
  has_changes "packages/gamedata" packages/gamedata/ packages/gamedata-dotnet/ packages/gamedata-npm/ && GAMEDATA=true
  has_changes "packages/api" packages/api/ packages/api-npm/ && API=true
  has_changes "packages/devdata" packages/devdata/ && DEVDATA=true
else
  case "$TARGET" in
    gamedata) GAMEDATA=true ;;
    api)      API=true ;;
    devdata)  DEVDATA=true ;;
  esac
fi

echo "gamedata=$GAMEDATA" >> "$GITHUB_OUTPUT"
echo "api=$API" >> "$GITHUB_OUTPUT"
echo "devdata=$DEVDATA" >> "$GITHUB_OUTPUT"

if [ "$GAMEDATA" = "true" ]; then
  VER=$(compute_version "packages/gamedata" "$BUMP")
  echo "gamedata-version=$VER" >> "$GITHUB_OUTPUT"
  echo "gamedata → v$VER"
fi
if [ "$API" = "true" ]; then
  VER=$(compute_version "packages/api" "$BUMP")
  echo "api-version=$VER" >> "$GITHUB_OUTPUT"
  echo "api → v$VER"
fi
if [ "$DEVDATA" = "true" ]; then
  VER=$(compute_version "packages/devdata" "$BUMP")
  echo "devdata-version=$VER" >> "$GITHUB_OUTPUT"
  echo "devdata → v$VER"
fi
