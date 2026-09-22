#!/usr/bin/env bash
set -euo pipefail

namespace=${1:?namespace is required}
release=${2:?release is required}
local_port=${3:?local port is required}
evidence_path=${4:?evidence path is required}
run_id=${GITHUB_RUN_ID:-local}
admin_email="smoke-${run_id}-${namespace}@example.com"
new_password="Smoke-$(openssl rand -hex 18)!"
forward_log=$(mktemp)

kubectl -n "$namespace" port-forward "service/${release}-frontend" "${local_port}:8080" >"$forward_log" 2>&1 &
forward_pid=$!
trap 'kill "$forward_pid" 2>/dev/null || true' EXIT

for _ in {1..60}; do
  curl --fail --silent "http://127.0.0.1:${local_port}/api/v1/health/ready" >/dev/null && break
  sleep 2
done
curl --fail --silent "http://127.0.0.1:${local_port}/api/v1/health/ready" >/dev/null

bootstrap_output=$(kubectl -n "$namespace" exec "deployment/${release}-api" -- \
  python -m app.bootstrap_admin "$admin_email" --full-name "Synthetic Smoke Administrator")
temporary_password=$(printf '%s\n' "$bootstrap_output" | sed -n 's/^One-time temporary password: //p')
test -n "$temporary_password"
echo "::add-mask::$temporary_password"
echo "::add-mask::$new_password"

token=$(curl --fail --silent --request POST \
  --data-urlencode username="$admin_email" \
  --data-urlencode password="$temporary_password" \
  "http://127.0.0.1:${local_port}/api/v1/login/access-token" | jq --raw-output .access_token)
echo "::add-mask::$token"
curl --fail --silent --request POST \
  --header "Authorization: Bearer $token" \
  --header "Content-Type: application/json" \
  --data "{\"current_password\":\"$temporary_password\",\"new_password\":\"$new_password\"}" \
  "http://127.0.0.1:${local_port}/api/v1/users/me/password" >/dev/null
token=$(curl --fail --silent --request POST \
  --data-urlencode username="$admin_email" \
  --data-urlencode password="$new_password" \
  "http://127.0.0.1:${local_port}/api/v1/login/access-token" | jq --raw-output .access_token)
echo "::add-mask::$token"

initial_contacts=$(curl --fail --silent \
  --header "Authorization: Bearer $token" \
  "http://127.0.0.1:${local_port}/api/v1/contacts?limit=1" | jq '.data | length')
test "$initial_contacts" -eq 0

import_id=$(curl --fail --silent \
  --header "Authorization: Bearer $token" \
  --form file=@fixtures/customer-data/valid-contacts.csv \
  "http://127.0.0.1:${local_port}/api/v1/imports" | jq --raw-output .id)
curl --fail --silent --request PUT \
  --header "Authorization: Bearer $token" \
  --header "Content-Type: application/json" \
  --data '{"mapping":{"email":"Email","first_name":"First Name","last_name":"Last Name","company":"Company","country_code":"Country","external_id":"External ID"}}' \
  "http://127.0.0.1:${local_port}/api/v1/imports/${import_id}/mapping" >/dev/null
curl --fail --silent --request POST \
  --header "Authorization: Bearer $token" \
  "http://127.0.0.1:${local_port}/api/v1/imports/${import_id}/validate" >/dev/null

status=unknown
for _ in {1..90}; do
  status=$(curl --fail --silent --header "Authorization: Bearer $token" \
    "http://127.0.0.1:${local_port}/api/v1/imports/${import_id}" | jq --raw-output .status)
  test "$status" != failed
  test "$status" = validated && break
  sleep 2
done
test "$status" = validated

curl --fail --silent --request POST \
  --header "Authorization: Bearer $token" \
  --header "Idempotency-Key: smoke-${run_id}-${namespace}" \
  "http://127.0.0.1:${local_port}/api/v1/imports/${import_id}/confirm" >/dev/null
for _ in {1..90}; do
  status=$(curl --fail --silent --header "Authorization: Bearer $token" \
    "http://127.0.0.1:${local_port}/api/v1/imports/${import_id}" | jq --raw-output .status)
  test "$status" != failed
  test "$status" = completed && break
  sleep 2
done
test "$status" = completed

contact_count=$(curl --fail --silent --get \
  --header "Authorization: Bearer $token" \
  --data-urlencode q=amelie.tremblay@example.com \
  "http://127.0.0.1:${local_port}/api/v1/contacts" | jq '.data | length')
test "$contact_count" -eq 1
version=$(curl --fail --silent "http://127.0.0.1:${local_port}/api/v1/version" | jq -c .)
mkdir -p "$(dirname "$evidence_path")"
jq -n \
  --arg namespace "$namespace" \
  --arg release "$release" \
  --arg status "$status" \
  --argjson contact_count "$contact_count" \
  --argjson version "$version" \
  '{namespace:$namespace,release:$release,import_status:$status,matching_contacts:$contact_count,version:$version,synthetic_data_only:true}' \
  >"$evidence_path"
