#!/usr/bin/env bash
# サービスの設定は terraform が所有し、CI はコンテナイメージだけを差し替える。
# `gcloud run services update` は対象が無いとサービスを作ってしまい、
# 環境変数が一つも無いサービスが terraform の管理外に生まれるため、先に存在を確かめる。
set -euo pipefail

if ! gcloud run services describe "${SERVICE_NAME}" \
  --project "${PROJECT_ID}" \
  --region "${REGION}" \
  --format="value(name)" >/dev/null 2>&1; then
  echo "::error::Cloud Run service '${SERVICE_NAME}' does not exist in ${PROJECT_ID}/${REGION}. Create it with terraform apply before deploying an image."
  exit 1
fi

gcloud run services update "${SERVICE_NAME}" \
  --image "${IMAGE}:${IMAGE_TAG}" \
  --project "${PROJECT_ID}" \
  --region "${REGION}" \
  --quiet
