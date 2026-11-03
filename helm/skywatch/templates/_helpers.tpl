{{- define "skywatch.frontendSelector" -}}
app.kubernetes.io/name: skywatch
app.kubernetes.io/component: frontend
{{- end -}}

{{- define "skywatch.backendSelector" -}}
app.kubernetes.io/name: skywatch
app.kubernetes.io/component: backend
{{- end -}}
