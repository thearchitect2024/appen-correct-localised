# AppenCorrect Helm Chart

This Helm chart deploys the AppenCorrect application to Kubernetes.

## Prerequisites

- Kubernetes 1.19+
- Helm 3.2.0+

## Installing the Chart

To install the chart with the release name `appencorrect`:

```bash
helm install appencorrect ./helm-charts/appencorrect
```

The command deploys AppenCorrect on the Kubernetes cluster in the default configuration. The [Parameters](#parameters) section lists the parameters that can be configured during installation.

> **Tip**: List all releases using `helm list`

## Uninstalling the Chart

To uninstall/delete the `appencorrect` deployment:

```bash
helm uninstall appencorrect
```

The command removes all the Kubernetes components associated with the chart and deletes the release.

## Parameters

### Global parameters

| Name                      | Description                                     | Value |
| ------------------------- | ----------------------------------------------- | ----- |
| `nameOverride`            | String to partially override appencorrect.fullname | `""` |
| `fullnameOverride`        | String to fully override appencorrect.fullname | `""` |

### Appencorrect parameters

| Name                      | Description                                     | Value |
| ------------------------- | ----------------------------------------------- | ----- |
| `replicaCount`            | Number of AppenCorrect replicas to deploy      | `3` |
| `image.repository`       | AppenCorrect image repository                   | `appencorrect` |
| `image.pullPolicy`        | AppenCorrect image pull policy                  | `IfNotPresent` |
| `image.tag`               | AppenCorrect image tag (immutable tags are recommended) | `latest` |

### Service parameters

| Name                      | Description                                     | Value |
| ------------------------- | ----------------------------------------------- | ----- |
| `service.type`            | Kubernetes service type                        | `ClusterIP` |
| `service.port`            | Service HTTP port                               | `80` |
| `service.targetPort`      | Service HTTP target port                        | `5006` |

### Ingress parameters

| Name                      | Description                                     | Value |
| ------------------------- | ----------------------------------------------- | ----- |
| `ingress.enabled`         | Enable ingress record generation for AppenCorrect | `false` |
| `ingress.className`       | IngressClass that will be used to implement the Ingress | `""` |
| `ingress.annotations`     | Additional annotations for the Ingress resource | `{}` |
| `ingress.hosts`           | An array of hosts to be covered with this ingress record | `[{"host": "appencorrect.local", "paths": [{"path": "/", "pathType": "Prefix"}]}]` |
| `ingress.tls`             | TLS configuration for additional hostname(s) to be covered with this ingress record | `[]` |

### Resource parameters

| Name                      | Description                                     | Value |
| ------------------------- | ----------------------------------------------- | ----- |
| `resources.limits.cpu`    | The resources limits for the AppenCorrect containers | `2` |
| `resources.limits.memory` | The resources limits for the AppenCorrect containers | `4Gi` |
| `resources.requests.cpu`  | The requested resources for the AppenCorrect containers | `1` |
| `resources.requests.memory` | The requested resources for the AppenCorrect containers | `2Gi` |

### Autoscaling parameters

| Name                      | Description                                     | Value |
| ------------------------- | ----------------------------------------------- | ----- |
| `autoscaling.enabled`     | Enable Horizontal POD autoscaling for AppenCorrect | `false` |
| `autoscaling.minReplicas` | Minimum number of AppenCorrect replicas        | `1` |
| `autoscaling.maxReplicas` | Maximum number of AppenCorrect replicas        | `100` |
| `autoscaling.targetCPUUtilizationPercentage` | Target CPU utilization percentage | `80` |

### Node parameters

| Name                      | Description                                     | Value |
| ------------------------- | ----------------------------------------------- | ----- |
| `nodeSelector`            | Node labels for pod assignment                 | `{"nodegroup": "spot"}` |
| `tolerations`             | Tolerations for pod assignment                  | `[]` |
| `affinity`                | Affinity for pod assignment                     | `{}` |

### Environment parameters

| Name                      | Description                                     | Value |
| ------------------------- | ----------------------------------------------- | ----- |
| `env.VLLM_URL`           | vLLM server URL for local LLM inference         | `http://vllm-service:8000` |
| `env.VLLM_MODEL`         | vLLM model name                                 | `Qwen/Qwen2.5-7B-Instruct` |

## Configuration and installation details

### Using environment variables

To pass environment variables to the AppenCorrect containers, you can use the `env` section in `values.yaml`:

```yaml
env:
  GEMINI_API_KEY: "your-api-key-here"
  OTHER_VAR: "value"
```

### Using a different image

To use a different AppenCorrect image:

```bash
helm install appencorrect ./helm-charts/appencorrect \
  --set image.repository=your-registry/appencorrect \
  --set image.tag=your-tag
```

### Using a different namespace

To install the chart in a different namespace:

```bash
helm install appencorrect ./helm-charts/appencorrect \
  --namespace adap \
  --create-namespace
```

## Examples

### Basic installation

```bash
helm install appencorrect ./helm-charts/appencorrect
```

### Installation with custom values

```bash
helm install appencorrect ./helm-charts/appencorrect \
  --set replicaCount=5 \
  --set resources.requests.memory=4Gi \
  --set resources.limits.memory=8Gi
```

### Installation with values file

```bash
helm install appencorrect ./helm-charts/appencorrect \
  --values my-values.yaml
```

## Troubleshooting

### Check deployment status

```bash
kubectl get deployment appencorrect -n adap
```

### Check pod logs

```bash
kubectl logs -l app.kubernetes.io/name=appencorrect -n adap
```

### Check service

```bash
kubectl get svc appencorrect-service -n adap
```

### Port forward for local testing

```bash
kubectl port-forward svc/appencorrect-service 8080:80 -n adap
```

Then access the application at `http://localhost:8080`
