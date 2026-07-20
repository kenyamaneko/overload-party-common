#!/usr/bin/env bash
set -euo pipefail

EPOCH=$(date +%s)
docker build --secret id=GO_MODULES_TOKEN,env=GO_MODULES_TOKEN -t "${IMAGE}:${EPOCH}-${GIT_SHA}" -t "${IMAGE}:${GIT_SHA}" -t "${IMAGE}:latest" .
docker push "${IMAGE}:${EPOCH}-${GIT_SHA}"
docker push "${IMAGE}:${GIT_SHA}"
docker push "${IMAGE}:latest"
