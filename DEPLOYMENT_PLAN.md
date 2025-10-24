# AppenCorrect Deployment Plan - AWS EKS with vLLM

## Executive Summary

This deployment plan outlines the architecture, configuration, and operational guidelines for deploying AppenCorrect on AWS EKS using local GPU inference with vLLM, KEDA autoscaling, and Karpenter node management.

**Configuration:** This plan uses **4096 token context window** to handle long texts (up to ~11,900 characters / 2,000+ words).

**Key Objectives:**
- Support 200-400 concurrent users in production
- Test capacity for 1000 concurrent users
- Achieve 3-6 second response times
- Enable scale-to-zero for cost optimization

**⚠️ Cost Consideration:** 4096 context requires **2x GPU pods** vs 2048 context:
- **Expected cost:** $800-1,500/month (depending on usage)
- **For 500-600 users:** ~$1,300-1,500/month
- **Trade-off:** Handles 3x longer texts but doubles GPU cost

---

## Architecture Overview

### Component Stack

```
┌────────────────────────────────────────────────────────────┐
│                    AWS Application Load Balancer           │
│                    (Public-facing, SSL/TLS)                │
└────────────────────────┬───────────────────────────────────┘
                         │
        ┌────────────────┴─────────────────┐
        │      Kubernetes Service          │
        │      (ClusterIP: flask-service)  │
        └────────────────┬─────────────────┘
                         │
    ┌────────────────────┴────────────────────┐
    │                                         │
┌───▼────────────────┐              ┌────────▼──────────┐
│  Flask API Layer   │              │  Flask API Layer  │
│  (CPU Pods 2-10)   │              │  (CPU Pods 2-10)  │
│  - Request Routing │     ...      │  - Request Routing│
│  - Validation      │              │  - Validation     │
│  - Cache Layer     │              │  - Cache Layer    │
│  - Authentication  │              │  - Authentication │
└───┬────────────────┘              └────────┬──────────┘
    │                                         │
    └────────────────┬────────────────────────┘
                     │ Internal K8s Network
        ┌────────────▼─────────────┐
        │   vLLM Inference Service │
        │   (ClusterIP: vllm-svc)  │
        └────────────┬─────────────┘
                     │
    ┌────────────────┼────────────────┐
    │                │                │
┌───▼──────────┐ ┌──▼───────────┐ ┌──▼───────────┐
│ vLLM GPU Pod │ │ vLLM GPU Pod │ │ vLLM GPU Pod │
│ (0-10 pods)  │ │ (0-10 pods)  │ │ (0-10 pods)  │
│ g6.xlarge    │ │ g6.xlarge    │ │ g6.xlarge    │
│ L4 GPU 24GB  │ │ L4 GPU 24GB  │ │ L4 GPU 24GB  │
│ Qwen 2.5 7B  │ │ Qwen 2.5 7B  │ │ Qwen 2.5 7B  │
└──────────────┘ └──────────────┘ └──────────────┘

┌────────────────────────────────────────────────────────────┐
│                Supporting Infrastructure                    │
├────────────────────────────────────────────────────────────┤
│ • Redis (ElastiCache cache.t4g.micro) - Response caching  │
│ • Prometheus - Metrics collection                          │
│ • KEDA - Event-driven autoscaling                         │
│ • Karpenter - Node lifecycle management                    │
└────────────────────────────────────────────────────────────┘
```

---

## Pod Configuration

### 1. Flask API Pods (CPU Layer)

**Purpose:** Handle HTTP requests, validation, authentication, and caching

```yaml
Deployment: appencorrect-flask
Replicas: 
  Min: 2 (always running)
  Max: 10 (peak capacity)
Instance Type: t3.medium Spot
  - 2 vCPU
  - 4 GiB RAM
  - Cost: $0.015/hour (Spot)
Resources:
  requests:
    cpu: 500m
    memory: 1Gi
  limits:
    cpu: 1000m
    memory: 2Gi
Container Image: appencorrect:vllm
Port: 5006
Health Check:
  path: /health
  interval: 10s
  timeout: 3s
```

**Capacity per Flask pod:**
- 500-1000 HTTP connections/second
- Not the bottleneck (GPU is)

**Total Flask capacity (10 pods):**
- 5,000-10,000 HTTP requests/second

**Scaling Strategy:**
- Horizontal Pod Autoscaler (HPA)
- Scale on CPU utilization > 70%
- Scale up: +2 pods every 30s
- Scale down: -1 pod every 60s

---

### 2. vLLM GPU Pods (Inference Layer)

**Purpose:** Run Qwen 2.5 7B model inference for grammar/spelling correction

```yaml
Deployment: vllm-inference
Replicas:
  Min: 0 (scale-to-zero!)
  Max: 10 (production)
  Max: 80 (load testing only)
Instance Type: g6.xlarge Spot
  - 4 vCPU
  - 16 GiB RAM
  - 1× NVIDIA L4 GPU (24GB VRAM)
  - Cost: $0.453/hour (Spot)
Node Selector:
  nvidia.com/gpu: "true"
  karpenter.sh/capacity-type: "spot"
Tolerations:
  - key: nvidia.com/gpu
    operator: Exists
    effect: NoSchedule
Resources:
  requests:
    cpu: 3000m
    memory: 12Gi
    nvidia.com/gpu: 1
  limits:
    cpu: 4000m
    memory: 15Gi
    nvidia.com/gpu: 1
vLLM Configuration:
  Model: Qwen/Qwen2.5-7B-Instruct
  max-model-len: 4096
  gpu-memory-utilization: 0.90
  max-num-seqs: 8
  enable-prefix-caching: true
  generation-config: vllm (CRITICAL)
```

**Capacity per GPU pod:**
- 8 concurrent inference requests
- ~2 requests/second throughput
- 3-6 second processing time per request

**Total GPU capacity (10 pods):**
- 80 concurrent inference requests
- 20 requests/second throughput
- **Supports 80-160 concurrent users**

**Scaling Strategy:**
- KEDA event-driven autoscaling
- Scale on queue depth > 10 per pod
- Scale on GPU utilization > 80%
- Cold start time: 60-90 seconds

---

## Autoscaling Configuration

### KEDA ScaledObject (GPU Pods)

```yaml
apiVersion: keda.sh/v1alpha1
kind: ScaledObject
metadata:
  name: vllm-gpu-scaler
  namespace: default
spec:
  scaleTargetRef:
    name: vllm-deployment
  
  minReplicaCount: 0                    # Scale to ZERO during idle
  maxReplicaCount: 10                   # Normal production max
  pollingInterval: 5                    # Check metrics every 5s
  cooldownPeriod: 30                    # Wait 30s idle before scale-down
  
  triggers:
  # Primary: Queue depth
  - type: prometheus
    metadata:
      serverAddress: http://prometheus:9090
      metricName: vllm_queue_depth
      threshold: '10'                   # Scale if queue > 10 per pod
      query: |
        sum(vllm_num_requests_waiting + vllm_num_requests_running) /
        (count(up{job="vllm"}) + 1)
  
  # Secondary: GPU utilization
  - type: prometheus
    metadata:
      serverAddress: http://prometheus:9090
      metricName: gpu_utilization
      threshold: '80'                   # Scale if GPU > 80%
      query: |
        avg(DCGM_FI_DEV_GPU_UTIL{pod=~"vllm.*"})
  
  # Scaling behavior
  behavior:
    scaleUp:
      stabilizationWindowSeconds: 0     # Immediate scale-up
      policies:
      - type: Percent
        value: 100                      # Double capacity
        periodSeconds: 15
      - type: Pods
        value: 5                        # Add 5 pods at a time
        periodSeconds: 15
    
    scaleDown:
      stabilizationWindowSeconds: 60    # Wait 60s before scale-down
      policies:
      - type: Pods
        value: 2                        # Remove 2 pods at a time
        periodSeconds: 30
```

### HPA Configuration (Flask Pods)

```yaml
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: flask-hpa
  namespace: default
spec:
  scaleTargetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: appencorrect-flask
  
  minReplicas: 2
  maxReplicas: 10
  
  metrics:
  - type: Resource
    resource:
      name: cpu
      target:
        type: Utilization
        averageUtilization: 70
  
  behavior:
    scaleUp:
      stabilizationWindowSeconds: 30
      policies:
      - type: Pods
        value: 2
        periodSeconds: 30
    scaleDown:
      stabilizationWindowSeconds: 120
      policies:
      - type: Pods
        value: 1
        periodSeconds: 60
```

---

## Karpenter Configuration

### NodePool for GPU Nodes

```yaml
apiVersion: karpenter.sh/v1beta1
kind: NodePool
metadata:
  name: gpu-spot-pool
spec:
  template:
    spec:
      requirements:
      - key: node.kubernetes.io/instance-type
        operator: In
        values: ["g6.xlarge"]
      - key: karpenter.sh/capacity-type
        operator: In
        values: ["spot"]                # Spot only for cost savings
      - key: kubernetes.io/arch
        operator: In
        values: ["amd64"]
      
      nodeClassRef:
        name: gpu-node-class
      
      taints:
      - key: nvidia.com/gpu
        effect: NoSchedule              # GPU nodes only for GPU workloads
  
  disruption:
    consolidationPolicy: WhenEmpty
    consolidateAfter: 30s               # Terminate idle nodes after 30s
  
  limits:
    cpu: 400                            # Max 100 nodes (4 CPU each)
    memory: 1600Gi

---
apiVersion: karpenter.k8s.aws/v1beta1
kind: EC2NodeClass
metadata:
  name: gpu-node-class
spec:
  amiFamily: AL2                        # Amazon Linux 2
  role: KarpenterNodeRole
  subnetSelectorTerms:
  - tags:
      karpenter.sh/discovery: ${CLUSTER_NAME}
  securityGroupSelectorTerms:
  - tags:
      karpenter.sh/discovery: ${CLUSTER_NAME}
  
  blockDeviceMappings:
  - deviceName: /dev/xvda
    ebs:
      volumeSize: 100Gi
      volumeType: gp3
      deleteOnTermination: true
  
  userData: |
    #!/bin/bash
    # Install NVIDIA drivers
    /usr/bin/nvidia-smi
```

### NodePool for CPU Nodes

```yaml
apiVersion: karpenter.sh/v1beta1
kind: NodePool
metadata:
  name: cpu-spot-pool
spec:
  template:
    spec:
      requirements:
      - key: node.kubernetes.io/instance-type
        operator: In
        values: ["t3.medium", "t3a.medium"]
      - key: karpenter.sh/capacity-type
        operator: In
        values: ["spot"]
      
      nodeClassRef:
        name: cpu-node-class
  
  disruption:
    consolidationPolicy: WhenEmpty
    consolidateAfter: 60s
  
  limits:
    cpu: 40                             # Max 20 nodes (2 CPU each)
```

---

## Cost Analysis

### Monthly Cost Breakdown (Production with 4096 Context)

| Component | Configuration | Unit Cost | Hours/Month | Monthly Cost |
|-----------|--------------|-----------|-------------|--------------|
| **Flask Pods** | 2× t3.medium Spot (always on) | $0.015/hr | 1,440 hrs | **$22** |
| **Flask Pods** | 2× t3.medium Spot (avg peak) | $0.015/hr | 352 hrs | **$5** |
| **GPU Pods (4096 ctx)** | 0-20× g6.xlarge Spot | $0.453/hr | 1,760 hrs* | **$797** |
| **ElastiCache Redis** | cache.t4g.micro | - | - | **$12** |
| **Application Load Balancer** | 1× ALB | - | - | **$23** |
| **EBS Storage** | 100GB GP3 | - | - | **$10** |
| **Data Transfer** | 100GB outbound | - | - | **$9** |
| **CloudWatch Logs** | 10GB/month | - | - | **$5** |
| **Total** | | | | **$883/month** |

*GPU hours calculation: 6 pods avg × 10 hrs/day × 22 business days = 1,320 hrs + 8 hrs weekend tests = 1,760 hrs

**⚠️ Cost Impact:** 4096 context requires 2x GPU pods vs 2048 context, **doubling GPU costs**.

### Cost Per Scenario (4096 Context)

| Scenario | Flask Pods | GPU Pods | Duration | Cost/Month |
|----------|------------|----------|----------|------------|
| **Idle** (nights/weekends) | 2 | 0 | 14 hrs/day | $62/month |
| **Low** (0-40 users) | 2 | 2-4 | 6 hrs/day | $220/month |
| **Medium** (40-100 users) | 2-4 | 6-10 | 8 hrs/day | $480/month |
| **High** (100-250 users) | 4-6 | 12-16 | 10 hrs/day | $850/month |
| **Peak** (250-400 users) | 6-10 | 16-20 | 2 hrs/day | $540/month |
| **Load Test** (1000 users) | 10 | 160 | 1 hour | $72/test |

**Note:** For 500-600 concurrent users, expect **~$1,300-1,500/month** with 4096 context.

### Budget Optimization Strategies

1. **Scale-to-Zero During Idle:** GPU pods scale to 0 during nights/weekends
2. **Spot Instances:** 44% cost savings vs On-Demand ($0.453 vs $0.805)
3. **Redis Caching:** 80%+ cache hit rate reduces GPU inference calls
4. **Prefix Caching:** vLLM caches system prompts for 30-40% speedup
5. **Right-Sized Pods:** t3.medium for Flask (not over-provisioned)
6. **Fast Termination:** Karpenter terminates idle nodes in 30-60s

**Expected Savings:** 85-90% vs always-on deployment

---

## Capacity Planning

### Concurrent User Capacity (4096 Context Window)

| Flask Pods | GPU Pods | Concurrent Users | Requests/Sec | Use Case |
|------------|----------|------------------|--------------|----------|
| 2 | 0 | 0 | 0 | Idle (cached only) |
| 2 | 2 | 20-40 | 4 | Light usage |
| 3 | 6 | 60-120 | 12 | Medium usage |
| 4 | 10 | 100-200 | 20 | Heavy usage |
| 6 | 20 | 200-400 | 40 | **Production peak** ✅ |
| 10 | 40 | 400-800 | 80 | Overload |
| 10 | 160 | 1000+ | 320+ | **Load testing** ✅ |

**Note:** 4096 context window requires 2x GPU pods vs 2048 context for same user capacity.

### Response Time SLAs

| Scenario | P50 Latency | P95 Latency | P99 Latency |
|----------|-------------|-------------|-------------|
| **Cache Hit** | 50ms | 100ms | 200ms |
| **GPU Inference (optimal)** | 2.5s | 3.5s | 5s |
| **GPU Inference (loaded)** | 3.5s | 5s | 8s |
| **Queue Wait (overload)** | 5s | 10s | 20s |
| **Cold Start** | 60s | 90s | 120s |

---

## Deployment Steps

### Prerequisites

1. **AWS Account with:**
   - EKS cluster (1.28+)
   - VPC with public/private subnets
   - IAM roles for Karpenter
   - ElastiCache Redis cluster

2. **Kubernetes Tools:**
   ```bash
   kubectl version --client
   helm version
   ```

3. **KEDA Installed:**
   ```bash
   helm repo add kedacore https://kedacore.github.io/charts
   helm install keda kedacore/keda --namespace keda --create-namespace
   ```

4. **Karpenter Installed:**
   ```bash
   helm repo add karpenter https://charts.karpenter.sh
   helm install karpenter karpenter/karpenter --namespace karpenter \
     --create-namespace \
     --set clusterName=${CLUSTER_NAME} \
     --set clusterEndpoint=${CLUSTER_ENDPOINT}
   ```

5. **Prometheus Installed:**
   ```bash
   helm repo add prometheus-community https://prometheus-community.github.io/helm-charts
   helm install prometheus prometheus-community/kube-prometheus-stack \
     --namespace monitoring --create-namespace
   ```

6. **NVIDIA GPU Operator:**
   ```bash
   helm repo add nvidia https://helm.ngc.nvidia.com/nvidia
   helm install gpu-operator nvidia/gpu-operator \
     --namespace gpu-operator --create-namespace
   ```

### Step 1: Deploy Karpenter NodePools

```bash
# Apply GPU NodePool
kubectl apply -f k8s/karpenter-gpu-nodepool.yaml

# Apply CPU NodePool
kubectl apply -f k8s/karpenter-cpu-nodepool.yaml

# Verify
kubectl get nodepools
```

### Step 2: Deploy Redis Cache

```bash
# ElastiCache via AWS Console or Terraform
# OR deploy in-cluster Redis (not recommended for production)
kubectl apply -f k8s/redis-deployment.yaml
```

### Step 3: Create ConfigMaps and Secrets

```bash
# vLLM configuration
kubectl create configmap vllm-config \
  --from-literal=VLLM_MODEL=Qwen/Qwen2.5-7B-Instruct \
  --from-literal=VLLM_MAX_MODEL_LEN=4096 \
  --from-literal=VLLM_GPU_MEMORY_UTILIZATION=0.90

# Redis connection
kubectl create secret generic redis-secret \
  --from-literal=REDIS_HOST=your-redis-endpoint.cache.amazonaws.com \
  --from-literal=REDIS_PORT=6379

# Application secrets
kubectl create secret generic app-secrets \
  --from-literal=SECRET_KEY=your-secret-key-here
```

### Step 4: Deploy vLLM GPU Pods

```bash
# Deploy vLLM inference service
kubectl apply -f k8s/vllm-deployment.yaml
kubectl apply -f k8s/vllm-service.yaml

# Verify (should be 0 pods initially)
kubectl get pods -l app=vllm
```

### Step 5: Deploy KEDA ScaledObject

```bash
# Deploy KEDA autoscaler for vLLM
kubectl apply -f k8s/keda-vllm-scaledobject.yaml

# Verify
kubectl get scaledobjects
```

### Step 6: Deploy Flask API Pods

```bash
# Deploy Flask application
kubectl apply -f k8s/flask-deployment.yaml
kubectl apply -f k8s/flask-service.yaml
kubectl apply -f k8s/flask-hpa.yaml

# Verify (should see 2 pods)
kubectl get pods -l app=flask
```

### Step 7: Deploy Application Load Balancer

```bash
# Deploy ALB Ingress
kubectl apply -f k8s/ingress.yaml

# Get ALB DNS name
kubectl get ingress appencorrect-ingress -o jsonpath='{.status.loadBalancer.ingress[0].hostname}'
```

### Step 8: Configure DNS

```bash
# Point your domain to ALB
# Create Route53 record or update DNS provider
# Example: appencorrect.yourdomain.com -> <alb-dns-name>
```

### Step 9: Enable SSL/TLS

```bash
# Install cert-manager
helm install cert-manager jetstack/cert-manager \
  --namespace cert-manager --create-namespace \
  --set installCRDs=true

# Apply ClusterIssuer for Let's Encrypt
kubectl apply -f k8s/cert-issuer.yaml

# Update Ingress with TLS
kubectl apply -f k8s/ingress-tls.yaml
```

### Step 10: Deploy Monitoring

```bash
# Deploy ServiceMonitors for Prometheus
kubectl apply -f k8s/servicemonitor-flask.yaml
kubectl apply -f k8s/servicemonitor-vllm.yaml

# Deploy Grafana dashboards
kubectl apply -f k8s/grafana-dashboard.yaml
```

---

## Monitoring and Observability

### Key Metrics to Track

#### Application Metrics
- Request rate (requests/second)
- Response time (P50, P95, P99)
- Error rate (4xx, 5xx)
- Cache hit rate (%)
- Queue depth (vLLM)

#### Infrastructure Metrics
- Flask pod CPU/Memory utilization
- GPU pod GPU/Memory utilization
- GPU inference throughput (tokens/sec)
- Node count (CPU and GPU)
- Pod count (Flask and vLLM)

#### Cost Metrics
- GPU hours used per day
- Cost per inference request
- Monthly burn rate
- Spot interruption rate

### Prometheus Queries

```promql
# Average response time
histogram_quantile(0.95, sum(rate(http_request_duration_seconds_bucket[5m])) by (le))

# GPU utilization
avg(DCGM_FI_DEV_GPU_UTIL{pod=~"vllm.*"})

# vLLM queue depth
sum(vllm_num_requests_waiting)

# Cache hit rate
sum(rate(cache_hits_total[5m])) / sum(rate(cache_requests_total[5m]))

# Cost per hour (approximate)
(count(up{job="flask"}) * 0.015) + (count(up{job="vllm"}) * 0.453)
```

### Grafana Dashboards

Create dashboards for:
1. **Application Performance:** Request rate, latency, errors
2. **GPU Utilization:** GPU%, memory, temperature, power
3. **Scaling Behavior:** Pod count over time, scale events
4. **Cost Tracking:** Hourly/daily/monthly cost projections
5. **User Experience:** Real user monitoring, session metrics

### Alerts

```yaml
# High error rate
- alert: HighErrorRate
  expr: sum(rate(http_requests_total{status=~"5.."}[5m])) / sum(rate(http_requests_total[5m])) > 0.05
  for: 5m
  annotations:
    summary: "Error rate above 5%"

# High queue depth
- alert: HighQueueDepth
  expr: sum(vllm_num_requests_waiting) > 50
  for: 2m
  annotations:
    summary: "vLLM queue depth above 50"

# GPU pod unavailable
- alert: NoGPUPods
  expr: count(up{job="vllm"}) == 0 and sum(vllm_num_requests_waiting) > 0
  for: 2m
  annotations:
    summary: "No GPU pods running but requests waiting"

# High response time
- alert: HighLatency
  expr: histogram_quantile(0.95, sum(rate(http_request_duration_seconds_bucket[5m])) by (le)) > 8
  for: 5m
  annotations:
    summary: "P95 latency above 8 seconds"

# Budget overrun
- alert: CostOverrun
  expr: (count(up{job="flask"}) * 0.015 + count(up{job="vllm"}) * 0.453) * 720 > 500
  for: 1h
  annotations:
    summary: "Projected monthly cost above $500"
```

---

## Load Testing

### Preparation

1. **Increase vLLM max replicas:**
   ```bash
   kubectl patch scaledobject vllm-gpu-scaler \
     -p '{"spec":{"maxReplicaCount":80}}' --type=merge
   ```

2. **Pre-warm cache:**
   ```bash
   # Send warm-up requests to cache common prompts
   for i in {1..100}; do
     curl -X POST https://your-domain.com/demo/check \
       -H "Content-Type: application/json" \
       -d '{"text":"Test sentence number '$i'"}'
   done
   ```

### JMeter Test Plan

```xml
<!-- Load test configuration -->
Thread Group:
  Number of Threads: 1000
  Ramp-Up Period: 60 seconds
  Loop Count: 10
  Duration: 600 seconds (10 minutes)

HTTP Request:
  Server: your-domain.com
  Port: 443
  Protocol: https
  Path: /demo/check
  Method: POST
  Body: {"text": "${text_sample}"}

CSV Data Set:
  File: test_sentences.csv
  Variable: text_sample
  Recycle on EOF: true
```

### Running Load Test

```bash
# Run JMeter in CLI mode
jmeter -n -t load_test_1000_users.jmx \
  -l results.jtl \
  -e -o report_html \
  -Jthreads=1000 \
  -Jrampup=60 \
  -Jduration=600

# Monitor scaling
watch -n 5 'kubectl get pods -l app=vllm | grep Running | wc -l'

# Monitor metrics
kubectl port-forward -n monitoring svc/prometheus 9090:9090
# Open http://localhost:9090
```

### Post-Test Actions

1. **Reset max replicas:**
   ```bash
   kubectl patch scaledobject vllm-gpu-scaler \
     -p '{"spec":{"maxReplicaCount":10}}' --type=merge
   ```

2. **Analyze results:**
   - Average response time
   - Error rate
   - Max concurrent GPU pods reached
   - Total cost for test duration

3. **Tune parameters if needed:**
   - Adjust `max-num-seqs` in vLLM
   - Tune KEDA scaling thresholds
   - Adjust HPA CPU targets

---

## Operational Procedures

### Daily Operations

- **Morning:** Check Grafana dashboards for overnight anomalies
- **Throughout day:** Monitor alert notifications
- **Evening:** Review cost burn rate and adjust if needed

### Weekly Maintenance

- **Review cost report:** Compare actual vs projected spend
- **Check spot interruption rate:** If > 10%, consider adding On-Demand fallback
- **Update dependencies:** Security patches for Flask, vLLM
- **Review error logs:** Identify and fix recurring issues
- **Capacity planning:** Adjust min/max replicas based on traffic patterns

### Monthly Tasks

- **Performance review:** Analyze P95/P99 latency trends
- **Cost optimization:** Review and optimize resource requests/limits
- **Model updates:** Test and deploy newer Qwen versions
- **Disaster recovery test:** Simulate and recover from failures
- **Security audit:** Review IAM roles, secrets, network policies

### Emergency Procedures

#### vLLM Pods Stuck in Pending

```bash
# Check node availability
kubectl get nodes
kubectl describe node <node-name>

# Check Karpenter logs
kubectl logs -n karpenter -l app.kubernetes.io/name=karpenter

# Manually provision node (if needed)
kubectl scale deployment vllm-deployment --replicas=0
kubectl scale deployment vllm-deployment --replicas=2
```

#### High Error Rate

```bash
# Check Flask logs
kubectl logs -l app=flask --tail=100

# Check vLLM logs
kubectl logs -l app=vllm --tail=100

# Restart unhealthy pods
kubectl delete pod -l app=flask --field-selector=status.phase=Failed
kubectl delete pod -l app=vllm --field-selector=status.phase=Failed
```

#### Cost Overrun

```bash
# Immediately scale down
kubectl patch scaledobject vllm-gpu-scaler \
  -p '{"spec":{"maxReplicaCount":5}}' --type=merge

# Check current pod count
kubectl get pods -l app=vllm -o wide

# Identify and remove stuck nodes
kubectl get nodes -l karpenter.sh/capacity-type=spot
kubectl delete node <node-name>
```

---

## Disaster Recovery

### Backup Strategy

1. **Application Code:** Git repository (already backed up)
2. **Configuration:** Kubernetes manifests in Git
3. **Redis Data:** ElastiCache automated snapshots (daily)
4. **Model Weights:** Cached in S3 by Hugging Face
5. **User Data:** SQLite database backed up to S3 daily

### Recovery Procedures

#### Complete Cluster Failure

```bash
# 1. Create new EKS cluster
eksctl create cluster -f cluster-config.yaml

# 2. Install core components
./scripts/install-core-components.sh

# 3. Deploy application
kubectl apply -f k8s/

# 4. Restore Redis data
aws elasticache restore-cache-cluster-from-snapshot \
  --cache-cluster-id appencorrect-redis \
  --snapshot-name daily-backup-latest

# 5. Update DNS to new ALB
aws route53 change-resource-record-sets ...
```

RTO (Recovery Time Objective): 30 minutes
RPO (Recovery Point Objective): 24 hours

---

## Security Considerations

### Network Security

- Private subnets for GPU nodes
- Security groups restrict traffic
- WAF rules on ALB (rate limiting, SQL injection)
- TLS 1.3 only for external traffic

### Pod Security

```yaml
securityContext:
  runAsNonRoot: true
  runAsUser: 1000
  fsGroup: 1000
  allowPrivilegeEscalation: false
  capabilities:
    drop:
    - ALL
```

### Secrets Management

- Kubernetes Secrets for sensitive data
- AWS Secrets Manager for production secrets
- Rotate secrets quarterly
- No hardcoded credentials in code

### Access Control

- RBAC for Kubernetes access
- IAM roles for service accounts (IRSA)
- MFA required for production access
- Audit logging enabled

---

## Optimization Opportunities

### Short-term (0-3 months)

1. **Install FlashInfer:** Reduce latency from 7s to 2-3s
2. **Tune vLLM parameters:** Optimize `max-num-seqs` for your workload
3. **Implement Redis clustering:** Improve cache availability
4. **Add APM tool:** Full request tracing (DataDog, New Relic)

### Medium-term (3-6 months)

1. **Multi-region deployment:** Reduce latency for global users
2. **Model distillation:** Use smaller Qwen 1.5B for simple requests
3. **Request batching:** Batch similar requests on Flask layer
4. **CDN integration:** Cache static assets and frequent responses

### Long-term (6-12 months)

1. **GPU instance optimization:** Test g5.xlarge, g6.2xlarge for better $/performance
2. **Custom fine-tuned model:** Train on your specific use cases
3. **Inference optimization:** Quantization (INT8) if accuracy permits
4. **Serverless inference:** AWS Lambda + Bedrock for extreme scale-to-zero

---

## Appendix

### A. Environment Variables

```bash
# Flask application
FLASK_ENV=production
VLLM_URL=http://vllm-service:8000
VLLM_MODEL=Qwen/Qwen2.5-7B-Instruct
REDIS_HOST=redis-service
REDIS_PORT=6379
SECRET_KEY=<random-secret>
LOG_LEVEL=INFO

# vLLM server
VLLM_MODEL=Qwen/Qwen2.5-7B-Instruct
VLLM_MAX_MODEL_LEN=4096
VLLM_GPU_MEMORY_UTILIZATION=0.90
VLLM_MAX_NUM_SEQS=8
HF_HOME=/model-cache
CUDA_VISIBLE_DEVICES=0
```

### B. Useful Commands

```bash
# Check GPU availability
kubectl get nodes -l nvidia.com/gpu=true

# Scale vLLM manually
kubectl scale deployment vllm-deployment --replicas=5

# Port forward to Flask
kubectl port-forward svc/flask-service 5006:5006

# Port forward to vLLM
kubectl port-forward svc/vllm-service 8000:8000

# Check vLLM logs
kubectl logs -l app=vllm --tail=50 -f

# Check KEDA scaling
kubectl describe scaledobject vllm-gpu-scaler

# Check Karpenter nodes
kubectl get nodepools
kubectl describe nodepool gpu-spot-pool

# Get current cost estimate
kubectl get pods -A -o json | jq '[.items[] | select(.spec.nodeName != null) | .spec.nodeName] | unique | length'
```

### C. Troubleshooting Guide

| Issue | Symptoms | Solution |
|-------|----------|----------|
| vLLM not detecting errors | Returns empty corrections | Restart vLLM with `--generation-config vllm` |
| High latency (>10s) | Slow responses | Check GPU utilization, scale up pods |
| Pods pending | No nodes available | Check Karpenter, increase limits |
| Out of memory | Pod OOMKilled | Reduce `gpu-memory-utilization` to 0.85 |
| High cost | Over budget | Check pod count, reduce max replicas |
| Cache miss | Low cache hit rate | Increase Redis memory, check TTL |
| Spot interruptions | Pods terminated | Add On-Demand fallback, increase diversity |

### D. Contact and Support

- **GitHub Issues:** https://github.com/thearchitect2024/appen-correct-localised/issues
- **Documentation:** https://github.com/thearchitect2024/appen-correct-localised
- **On-call:** (Setup PagerDuty or similar)

---

## Revision History

| Version | Date | Author | Changes |
|---------|------|--------|---------|
| 1.0 | 2025-10-24 | AI Assistant | Initial deployment plan |

---

**Document Status:** ✅ Ready for Production Deployment

**Next Review Date:** 2025-11-24

