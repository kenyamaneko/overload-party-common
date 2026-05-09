#!/usr/bin/env bash
# audience=cloudsmith は overload-party-infra の cloudsmith_oidc.claims.aud と一致させる契約。
# 値を変えると Cloudsmith 側で OIDC token が拒否される。
set -euo pipefail

github_token="$(curl -fsSL \
  -H "Authorization: bearer ${ACTIONS_ID_TOKEN_REQUEST_TOKEN}" \
  "${ACTIONS_ID_TOKEN_REQUEST_URL}&audience=cloudsmith" | jq -r '.value')"

payload="$(jq -nc \
  --arg token "${github_token}" \
  --arg slug "${SERVICE_SLUG}" \
  '{oidc_token: $token, service_slug: $slug}')"

response="$(curl -fsSL -X POST \
  -H "Content-Type: application/json" \
  -d "${payload}" \
  "https://api.cloudsmith.io/openid/keyandnotes/")"

cloudsmith_token="$(echo "${response}" | jq -r '.token')"
if [ -z "${cloudsmith_token}" ] || [ "${cloudsmith_token}" = "null" ]; then
  echo "::error::Cloudsmith OIDC exchange did not return a token"
  exit 1
fi

echo "::add-mask::${cloudsmith_token}"
echo "token=${cloudsmith_token}" >> "${GITHUB_OUTPUT}"
