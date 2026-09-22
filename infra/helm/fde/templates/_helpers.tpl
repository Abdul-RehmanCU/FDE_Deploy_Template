{{- define "fde.name" -}}fde{{- end -}}
{{- define "fde.fullname" -}}{{ printf "fde-%s-%s" .Values.customer .Values.environment | trunc 63 | trimSuffix "-" }}{{- end -}}
{{- define "fde.labels" -}}
app.kubernetes.io/name: {{ include "fde.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
app.kubernetes.io/version: {{ .Values.appVersion | quote }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
fde.dev/customer: {{ .Values.customer | quote }}
fde.dev/environment: {{ .Values.environment | quote }}
{{- end -}}
{{- define "fde.backendImage" -}}{{ printf "%s@%s" .Values.images.backend.repository .Values.images.backend.digest }}{{- end -}}
{{- define "fde.frontendImage" -}}{{ printf "%s@%s" .Values.images.frontend.repository .Values.images.frontend.digest }}{{- end -}}
{{- define "fde.secretVolume" -}}
- name: runtime-secrets
  {{- if .Values.secretProvider.enabled }}
  csi:
    driver: secrets-store-gke.csi.k8s.io
    readOnly: true
    volumeAttributes:
      secretProviderClass: {{ include "fde.fullname" . }}
  {{- else }}
  secret:
    secretName: {{ .Values.secretProvider.kubernetesSecretName }}
  {{- end }}
- name: runtime-tmp
  emptyDir: {}
- name: local-storage
  emptyDir: {}
{{- end -}}
{{- define "fde.secretMount" -}}
- name: runtime-secrets
  mountPath: /var/run/secrets/fde
  readOnly: true
- name: runtime-tmp
  mountPath: /tmp
- name: local-storage
  mountPath: {{ .Values.storage.localRoot }}
{{- end -}}
{{- define "fde.backendEnv" -}}
- { name: DATABASE_URL_FILE, value: /var/run/secrets/fde/database-url }
- { name: REDIS_URL_FILE, value: /var/run/secrets/fde/redis-url }
- { name: SECRET_KEY_FILE, value: /var/run/secrets/fde/secret-key }
- { name: BACKEND_CORS_ORIGINS, value: {{ .Values.backend.corsOrigins | quote }} }
- { name: DB_POOL_SIZE, value: {{ .Values.backend.dbPoolSize | quote }} }
- { name: DB_MAX_OVERFLOW, value: {{ .Values.backend.dbMaxOverflow | quote }} }
- { name: STORAGE_BACKEND, value: {{ .Values.storage.backend | quote }} }
- { name: STORAGE_LOCAL_ROOT, value: {{ .Values.storage.localRoot | quote }} }
- { name: GCS_BUCKET, value: {{ .Values.storage.gcsBucket | quote }} }
- { name: APP_ENVIRONMENT, value: {{ .Values.environment | quote }} }
- { name: APP_VERSION, value: {{ .Values.appVersion | quote }} }
- { name: TMPDIR, value: /tmp }
{{- if .Values.observability.enabled }}
- { name: OTEL_EXPORTER_OTLP_ENDPOINT, value: {{ .Values.observability.otlpEndpoint | quote }} }
- { name: OTEL_EXPORTER_OTLP_PROTOCOL, value: grpc }
- { name: OTEL_RESOURCE_ATTRIBUTES, value: {{ printf "deployment.environment=%s,service.version=%s" .Values.environment .Values.appVersion | quote }} }
{{- end }}
{{- end -}}
