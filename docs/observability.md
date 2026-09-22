# Observability guide

The compact observability stack is internal to the cluster. It combines an OpenTelemetry collector, Prometheus, Alertmanager, Loki, Tempo, Grafana, and Grafana Alloy with bounded retention and resource requests suitable for the short-lived demo.

## Signals

### Metrics

The API exposes internal Prometheus metrics separately from public application routes. The worker exposes `:9100/metrics` from its main process. Dashboards and rules cover:

- request throughput, error ratio, and latency;
- accepted, invalid, duplicate, existing, inserted, and skipped import outcomes;
- queued/running/succeeded/failed/cancelled jobs and oldest queue age;
- job attempts and duration;
- worker up and collection-success state;
- database connections by bounded state.

Metric labels must remain bounded. Do not use emails, filenames, import IDs, job IDs, request IDs, customer-provided values, or exception strings as labels.

### Logs

Application logs are structured JSON. Access logging and OpenTelemetry URL attributes omit query strings. Tokens, passwords, CSV contents, contact fields, temporary passwords, database URLs, Redis URLs, mounted secret contents, and arbitrary customer identifiers are forbidden.

Alloy collects container logs into Loki with a controlled label set. Search correlation IDs as fields rather than promoting them to high-cardinality labels.

### Traces

HTTP requests, SQLAlchemy, Redis, Celery publication, and worker execution use OpenTelemetry. Propagate W3C `traceparent` through the transactional outbox payload. Tempo stores the bounded demo trace history.

Before publishing trace evidence, confirm request URLs contain no query string and attributes contain no contact data or authorization material.

## Access

Grafana and application access use authenticated Kubernetes port forwarding. The chart does not create a public dashboard or load balancer by default.

```bash
kubectl -n observability port-forward service/fde-observability-grafana 3000:3000
kubectl -n CUSTOMER-ENV port-forward service/fde-CUSTOMER-ENV-frontend 8080:8080
```

Record the namespace, command start/end time, operator, and reason. Stop port-forward processes after evidence collection.

## Dashboards

The provisioned Grafana dashboard should answer:

1. Is the API available, and did error ratio or latency change?
2. Are validation/confirmation outcomes behaving as expected?
3. Is queue age growing, are attempts increasing, or is the worker missing?
4. Are database connections bounded?
5. Can a request be correlated to the background job without exposing PII?

Capture dashboard screenshots only after panels contain deterministic synthetic activity. Label each screenshot with tested commit, environment, time window, and whether it came from kind or GKE.

## Alerts

The stack defines internal alerts for unavailable API, elevated error ratio, oldest queued job, increased failed jobs, and worker heartbeat loss. For each alert drill, record:

- the exact controlled trigger;
- first pending and firing timestamps;
- relevant metric expression and value;
- resolution action and resolved timestamp;
- screenshots of firing and resolved states;
- confirmation that no external notification target was configured.

Do not weaken thresholds simply to produce a screenshot. Use deterministic traffic or bounded failure injection.

## Correlation evidence

For one synthetic import:

1. record the client request ID and trace ID;
2. locate the API span and outbox publication span;
3. locate the worker span with the same trace context;
4. find API and worker logs by trace ID;
5. show the corresponding job/import metrics;
6. verify no contact value appears in labels or log fields.

The sanitized evidence package may include screenshots and selected redacted JSON summaries. It must not include raw browser traces, auth storage, bearer headers, full cluster logs, or telemetry database exports.
