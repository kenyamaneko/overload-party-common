#!/usr/bin/env bash
set -euo pipefail

docker build --secret id=GO_MODULES_TOKEN,env=GO_MODULES_TOKEN -t "${IMAGE}:${GIT_SHA}" -t "${IMAGE}:latest" .
docker push "${IMAGE}:${GIT_SHA}"
docker push "${IMAGE}:latest"
