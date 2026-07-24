#!/usr/bin/env bash
set -euo pipefail

# private Go module 依存が無いビルドではトークンを渡さないため、ビルドシークレットの引き渡しを条件付きにする
if [ -n "${GO_MODULES_TOKEN}" ]; then
  docker build --secret id=GO_MODULES_TOKEN,env=GO_MODULES_TOKEN -t "${IMAGE}:${GIT_SHA}" -t "${IMAGE}:latest" .
else
  docker build -t "${IMAGE}:${GIT_SHA}" -t "${IMAGE}:latest" .
fi

docker push "${IMAGE}:${GIT_SHA}"
docker push "${IMAGE}:latest"
