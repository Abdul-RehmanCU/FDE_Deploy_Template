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
{{- define "fde.backendImage" -}}
{{- if .Values.secretProvider.enabled -}}{{ printf "%s@%s" .Values.images.backend.repository .Values.images.backend.digest }}{{- else -}}{{ printf "%s:%s" .Values.images.backend.repository .Values.images.backend.tag }}{{- end -}}
{{- end -}}
{{- define "fde.frontendImage" -}}
{{- if .Values.secretProvider.enabled -}}{{ printf "%s@%s" .Values.images.frontend.repository .Values.images.frontend.digest }}{{- else -}}{{ printf "%s:%s" .Values.images.frontend.repository .Values.images.frontend.tag }}{{- end -}}
{{- end -}}
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
  {{- if eq .Values.storage.backend "local" }}
  persistentVolumeClaim:
    claimName: {{ include "fde.fullname" . }}-local-storage
  {{- else }}
  emptyDir: {}
  {{- end }}
{{- if eq .Values.profile "managed" }}
- name: managed-tls
  emptyDir: { medium: Memory }
{{- end }}
{{- end -}}
{{- define "fde.secretMount" -}}
- name: runtime-secrets
  mountPath: /var/run/secrets/fde
  readOnly: true
{{- end -}}
{{- define "fde.backendMounts" -}}
{{- include "fde.secretMount" . }}
- name: runtime-tmp
  mountPath: /tmp
- name: local-storage
  mountPath: {{ .Values.storage.localRoot }}
{{- if eq .Values.profile "managed" }}
- name: managed-tls
  mountPath: /var/run/tls
  readOnly: true
{{- end }}
{{- end -}}
{{- define "fde.managedTlsInit" -}}
{{- if eq .Values.profile "managed" }}
- name: prepare-managed-tls
  image: {{ include "fde.backendImage" . }}
  imagePullPolicy: {{ .Values.images.backend.pullPolicy }}
  command: ["sh", "-ec", "cp /var/run/secrets/fde/redis-ca.pem /var/run/tls/redis-ca.pem; cp /var/run/secrets/fde/database-root-ca.pem /var/run/tls/database-root-ca.pem; cp /var/run/secrets/fde/database-client-cert.pem /var/run/tls/database-client-cert.pem; cp /var/run/secrets/fde/database-client-key.pem /var/run/tls/database-client-key.pem; chmod 0644 /var/run/tls/*.pem; chmod 0600 /var/run/tls/database-client-key.pem"]
  volumeMounts:
    {{- include "fde.secretMount" . | nindent 4 }}
    - { name: managed-tls, mountPath: /var/run/tls }
  securityContext:
    allowPrivilegeEscalation: false
    readOnlyRootFilesystem: true
    capabilities: { drop: ["ALL"] }
{{- end }}
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
- { name: PROJECT_NAME, value: {{ .Values.branding.name | quote }} }
- { name: TMPDIR, value: /tmp }
{{- if eq .Values.profile "managed" }}
- { name: REDIS_CA_FILE, value: /var/run/tls/redis-ca.pem }
- { name: DATABASE_SSLROOTCERT_FILE, value: /var/run/tls/database-root-ca.pem }
- { name: DATABASE_SSLCERT_FILE, value: /var/run/tls/database-client-cert.pem }
- { name: DATABASE_SSLKEY_FILE, value: /var/run/tls/database-client-key.pem }
- { name: DATABASE_SSLMODE, value: verify-ca }
{{- end }}
{{- if .Values.observability.enabled }}
- { name: OTEL_EXPORTER_OTLP_ENDPOINT, value: {{ .Values.observability.otlpEndpoint | quote }} }
- { name: OTEL_EXPORTER_OTLP_PROTOCOL, value: grpc }
- { name: OTEL_RESOURCE_ATTRIBUTES, value: {{ printf "deployment.environment=%s,service.version=%s" .Values.environment .Values.appVersion | quote }} }
{{- end }}
{{- end -}}
