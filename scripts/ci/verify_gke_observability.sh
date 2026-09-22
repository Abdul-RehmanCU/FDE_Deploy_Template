#!/usr/bin/env bash
set -euo pipefail

staging_trace=${1:?staging trace id is required}
production_trace=${2:?production-demo trace id is required}
evidence_dir=${3:?evidence directory is required}
customer=${CUSTOMER:?CUSTOMER is required}
mkdir -p "$evidence_dir"

grafana_password=$(kubectl -n observability get secret fde-grafana-admin -o jsonpath='{.data.password}' | base64 --decode)
echo "::add-mask::$grafana_password"
pids=()
cleanup() {
  if declare -F restore_production_best_effort >/dev/null && test "${production_restored:-0}" -ne 1; then
    restore_production_best_effort
  fi
  for pid in "${pids[@]}"; do kill "$pid" 2>/dev/null || true; done
}
trap cleanup EXIT
kubectl -n observability port-forward service/fde-prometheus 29090:9090 > "$RUNNER_TEMP/gke-prometheus-forward.log" 2>&1 &
pids+=("$!")
kubectl -n observability port-forward service/fde-loki 23100:3100 > "$RUNNER_TEMP/gke-loki-forward.log" 2>&1 &
pids+=("$!")
kubectl -n observability port-forward service/fde-tempo 23200:3200 > "$RUNNER_TEMP/gke-tempo-forward.log" 2>&1 &
pids+=("$!")
kubectl -n observability port-forward service/fde-grafana 23000:3000 > "$RUNNER_TEMP/gke-grafana-forward.log" 2>&1 &
pids+=("$!")
kubectl -n observability port-forward service/fde-alertmanager 29093:9093 > "$RUNNER_TEMP/gke-alertmanager-forward.log" 2>&1 &
pids+=("$!")

for _ in {1..60}; do
  if curl --fail --silent http://127.0.0.1:29090/-/ready >/dev/null && \
     curl --fail --silent http://127.0.0.1:23100/ready >/dev/null && \
     curl --fail --silent http://127.0.0.1:23200/ready >/dev/null && \
     curl --fail --silent http://127.0.0.1:23000/api/health >/dev/null; then
    break
  fi
  sleep 2
done

prom_value() {
  curl --fail --silent --get --data-urlencode "query=$1" http://127.0.0.1:29090/api/v1/query \
    | jq -r '.data.result[0].value[1] // "0"'
}

jq -n '{}' > "$evidence_dir/gke-metrics-summary.json"
for namespace in staging production-demo; do
  for _ in {1..60}; do
    api_up=$(prom_value "sum(up{job=\"fde-api\",namespace=\"$namespace\"})")
    worker_up=$(prom_value "sum(fde_worker_up{namespace=\"$namespace\"})")
    http_count=$(prom_value "sum(http_server_request_duration_seconds_count{namespace=\"$namespace\"})")
    import_rows=$(prom_value "count(fde_import_rows{namespace=\"$namespace\"})")
    oldest_job=$(prom_value "count(fde_oldest_queued_job_seconds{namespace=\"$namespace\"})")
    database_connections=$(prom_value "count(fde_database_connections{namespace=\"$namespace\"})")
    if awk -v a="$api_up" -v w="$worker_up" -v h="$http_count" -v i="$import_rows" -v o="$oldest_job" -v d="$database_connections" \
      'BEGIN { exit !(a>=2 && w>=1 && h>0 && i>0 && o>0 && d>0) }'; then break; fi
    sleep 2
  done
  awk -v a="$api_up" -v w="$worker_up" -v h="$http_count" -v i="$import_rows" -v o="$oldest_job" -v d="$database_connections" \
    'BEGIN { exit !(a>=2 && w>=1 && h>0 && i>0 && o>0 && d>0) }'
  jq --arg namespace "$namespace" --arg api "$api_up" --arg worker "$worker_up" \
    --arg http "$http_count" --arg imports "$import_rows" --arg oldest "$oldest_job" --arg database "$database_connections" \
    '.[$namespace]={api_up:($api|tonumber),worker_up:($worker|tonumber),http_requests:($http|tonumber),import_series:($imports|tonumber),oldest_job_series:($oldest|tonumber),database_series:($database|tonumber)}' \
    "$evidence_dir/gke-metrics-summary.json" > "$evidence_dir/gke-metrics-summary.tmp"
  mv "$evidence_dir/gke-metrics-summary.tmp" "$evidence_dir/gke-metrics-summary.json"
done

verify_trace() {
  local namespace=$1 trace_id=$2
  local trace_file="$evidence_dir/${namespace}-tempo-trace.json"
  local services_file="$evidence_dir/${namespace}-trace-services.txt"
  printf '{"trace":{"resourceSpans":[]}}\n' > "$trace_file"
  local services="" status=000
  for _ in {1..60}; do
    status=$(curl --silent --output "$trace_file" --write-out '%{http_code}' "http://127.0.0.1:23200/api/v2/traces/$trace_id" || true)
    if test "$status" = 200; then
      services=$(jq -r '.trace.resourceSpans[]?.resource.attributes[]? | select(.key == "service.name") | .value.stringValue' "$trace_file" | sort -u)
      printf '%s\n' "$services" > "$services_file"
      if grep -qx fde-api <<<"$services" && grep -qx fde-outbox-publisher <<<"$services" && grep -qx fde-worker <<<"$services"; then break; fi
    fi
    sleep 2
  done
  grep -qx fde-api <<<"$services"
  grep -qx fde-outbox-publisher <<<"$services"
  grep -qx fde-worker <<<"$services"

  trace_logs="$evidence_dir/${namespace}-loki-trace-last.json"
  printf '{"data":{"result":[]}}\n' > "$trace_logs"
  for _ in {1..60}; do
    if ! curl --fail --silent --get \
      --data-urlencode "query={namespace=\"$namespace\"} | json | trace_id=\"$trace_id\"" \
      --data-urlencode "start=$(date -u -d '60 minutes ago' +%s)000000000" \
      http://127.0.0.1:23100/loki/api/v1/query_range > "$trace_logs"; then
      printf '{"data":{"result":[]}}\n' > "$trace_logs"
    fi
    api_logs=$(jq '[.data.result[] | select(.stream.container | test("api")) | .values[]] | length' "$trace_logs")
    publisher_logs=$(jq '[.data.result[] | select(.stream.container | test("publisher")) | .values[]] | length' "$trace_logs")
    worker_logs=$(jq '[.data.result[] | select(.stream.container | test("worker")) | .values[]] | length' "$trace_logs")
    if test "$api_logs" -gt 0 && test "$publisher_logs" -gt 0 && test "$worker_logs" -gt 0; then break; fi
    sleep 2
  done
  test "$api_logs" -gt 0 && test "$publisher_logs" -gt 0 && test "$worker_logs" -gt 0
  jq -n --arg namespace "$namespace" --arg trace_id "$trace_id" \
    --argjson api "$api_logs" --argjson publisher "$publisher_logs" --argjson worker "$worker_logs" \
    '{namespace:$namespace,trace_id:$trace_id,log_counts:{api:$api,publisher:$publisher,worker:$worker},pii_included:false}' \
    > "$evidence_dir/${namespace}-loki-trace-summary.json"
}

verify_trace staging "$staging_trace"
verify_trace production-demo "$production_trace"
for namespace in staging production-demo; do
  trace_id=$staging_trace
  test "$namespace" = production-demo && trace_id=$production_trace
  for component in api publisher worker; do
    kubectl -n "$namespace" logs --all-containers --prefix --tail=1000 \
      --selector="app.kubernetes.io/component=$component" | grep "$trace_id" \
      > "$evidence_dir/${namespace}-${component}-trace-logs.txt" || true
  done
done

release="fde-${customer}-production-demo"
production_restored=0
restore_production_best_effort() {
  kubectl -n production-demo scale "deployment/${release}-api" --replicas=2 >/dev/null 2>&1 || true
  kubectl -n production-demo rollout status "deployment/${release}-api" --timeout=180s >/dev/null 2>&1 || true
}
restore_production_strict() {
  kubectl -n production-demo scale "deployment/${release}-api" --replicas=2
  kubectl -n production-demo rollout status "deployment/${release}-api" --timeout=180s
  production_restored=1
}
kubectl -n production-demo scale "deployment/${release}-api" --replicas=0
for _ in {1..120}; do
  staging_up=$(prom_value 'sum(up{job="fde-api",namespace="staging"})')
  curl --fail --silent http://127.0.0.1:29093/api/v2/alerts > "$evidence_dir/gke-alert-firing.json"
  if awk -v value="$staging_up" 'BEGIN { exit !(value>=2) }' && \
     jq -e 'any(.[]; .labels.alertname == "FDEApiUnavailable" and .labels.namespace == "production-demo") and (any(.[]; .labels.alertname == "FDEApiUnavailable" and .labels.namespace == "staging") | not)' "$evidence_dir/gke-alert-firing.json" >/dev/null; then break; fi
  sleep 3
done
awk -v value="$staging_up" 'BEGIN { exit !(value>=2) }'
jq -e 'any(.[]; .labels.alertname == "FDEApiUnavailable" and .labels.namespace == "production-demo")' "$evidence_dir/gke-alert-firing.json" >/dev/null
jq -e 'any(.[]; .labels.alertname == "FDEApiUnavailable" and .labels.namespace == "staging") | not' "$evidence_dir/gke-alert-firing.json" >/dev/null
jq -n --arg staging_up "$staging_up" '{production_demo_firing:true,staging_alert_absent:true,staging_api_up:($staging_up|tonumber)}' \
  > "$evidence_dir/gke-alert-isolation.json"
GRAFANA_URL=http://127.0.0.1:23000 ALERTMANAGER_URL=http://127.0.0.1:29093 \
  GRAFANA_USER=admin GRAFANA_PASSWORD="$grafana_password" TRACE_ID="$production_trace" \
  LOKI_NAMESPACE=production-demo OUTPUT_DIR="$evidence_dir" ALERT_PHASE=firing \
  bun scripts/ci/capture_observability_evidence.ts

restore_production_strict
jq -n '{production_demo_api_restored:true,replicas:2,rollout_ready:true}' > "$evidence_dir/gke-production-restoration.json"
for _ in {1..60}; do
  curl --fail --silent http://127.0.0.1:29093/api/v2/alerts > "$evidence_dir/gke-alert-resolved.json"
  if ! jq -e 'any(.[]; .labels.alertname == "FDEApiUnavailable" and .labels.namespace == "production-demo")' "$evidence_dir/gke-alert-resolved.json" >/dev/null; then break; fi
  sleep 3
done
! jq -e 'any(.[]; .labels.alertname == "FDEApiUnavailable" and .labels.namespace == "production-demo")' "$evidence_dir/gke-alert-resolved.json" >/dev/null
GRAFANA_URL=http://127.0.0.1:23000 ALERTMANAGER_URL=http://127.0.0.1:29093 \
  GRAFANA_USER=admin GRAFANA_PASSWORD="$grafana_password" TRACE_ID="$production_trace" \
  LOKI_NAMESPACE=production-demo OUTPUT_DIR="$evidence_dir" ALERT_PHASE=resolved \
  bun scripts/ci/capture_observability_evidence.ts
