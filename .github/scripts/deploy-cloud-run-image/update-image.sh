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

# タグは後から別のイメージへ付け替えられるため、stg で確かめた物と同じ物が prod に載るよう digest に固定して反映する。
if ! DIGEST="$(gcloud artifacts docker images describe "${IMAGE}:${IMAGE_TAG}" \
  --project "${REGISTRY_PROJECT_ID}" \
  --format="value(image_summary.digest)")" || [ -z "${DIGEST}" ]; then
  echo "::error::Could not resolve the digest of '${IMAGE}:${IMAGE_TAG}' in Artifact Registry. Push the image for this commit before deploying it."
  exit 1
fi

gcloud run services update "${SERVICE_NAME}" \
  --image "${IMAGE}@${DIGEST}" \
  --project "${PROJECT_ID}" \
  --region "${REGION}" \
  --quiet
