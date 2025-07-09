# 🚀 Cloud Deployment Guide

This guide covers the complete deployment process for running the Client Tracker Assistant on cloud infrastructure with GPU support.

## Architecture Overview

```
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│   GitHub Repo   │────▶│      GHCR       │────▶│    Kubernetes   │
│                 │     │  Container Reg  │     │   GPU Cluster   │
└─────────────────┘     └─────────────────┘     └─────────────────┘
                                                         │
                                ┌────────────────────────┼────────────────────────┐
                                │                        │                        │
                        ┌───────▼───────┐       ┌───────▼───────┐       ┌────────▼────────┐
                        │   Ollama Pod  │       │   API Pods    │       │   Pinecone      │
                        │  (A100 GPU)   │       │   (3 replicas)│       │  Vector Store   │
                        └───────────────┘       └───────────────┘       └─────────────────┘
                                │                        │                        │
                                └────────────────────────┴────────────────────────┘
                                                    │
                                            ┌───────▼───────┐
                                            │  REST API     │
                                            │  Endpoint     │
                                            └───────────────┘
```

## Prerequisites

- Kubernetes cluster with GPU nodes (NVIDIA A100 recommended)
- ArgoCD installed on the cluster
- GitHub repository access
- Pinecone account and API key
- kubectl configured to access your cluster

## Deployment Steps

### 1. Configure Secrets

First, create the necessary secrets in your Kubernetes cluster:

```bash
# Create namespace
kubectl create namespace client-tracker

# Create Pinecone secret
kubectl create secret generic client-tracker-secrets \
  --from-literal=pinecone-api-key=YOUR_PINECONE_API_KEY \
  -n client-tracker

# Create GitHub registry secret (if private)
kubectl create secret docker-registry ghcr-secret \
  --docker-server=ghcr.io \
  --docker-username=YOUR_GITHUB_USERNAME \
  --docker-password=YOUR_GITHUB_TOKEN \
  -n client-tracker
```

### 2. Deploy with ArgoCD

#### Option A: Using ArgoCD CLI

```bash
# Create the ArgoCD application
argocd app create client-tracker \
  --repo https://github.com/your-org/client-tracker-assistant.git \
  --path k8s/overlays/production \
  --dest-server https://kubernetes.default.svc \
  --dest-namespace client-tracker \
  --sync-policy automated \
  --self-heal \
  --auto-prune

# Sync the application
argocd app sync client-tracker
```

#### Option B: Using kubectl

```bash
# Apply the ArgoCD application manifest
kubectl apply -f argocd/application.yaml
```

### 3. Verify Deployment

Check that all components are running:

```bash
# Check pods
kubectl get pods -n client-tracker

# Expected output:
# NAME                                  READY   STATUS    RESTARTS   AGE
# ollama-7b9f8c5d6-xxxxx               1/1     Running   0          5m
# client-tracker-api-5d7b9c6f8-xxxxx   1/1     Running   0          5m
# client-tracker-api-5d7b9c6f8-yyyyy   1/1     Running   0          5m
# client-tracker-api-5d7b9c6f8-zzzzz   1/1     Running   0          5m

# Check services
kubectl get svc -n client-tracker

# Get the external endpoint
kubectl get svc client-tracker-api-service -n client-tracker -o jsonpath='{.status.loadBalancer.ingress[0].ip}'
```

### 4. Initial Model Loading

The Ollama models will be automatically pulled during the init container phase. Monitor the progress:

```bash
# Watch init container logs
kubectl logs -f deployment/client-tracker-api -c model-loader -n client-tracker
```

## Configuration

### Environment Variables

Key environment variables can be configured in `k8s/base/configmap.yaml`:

- `OLLAMA_HOST`: Ollama service endpoint
- `VECTOR_DB_PATH`: Path for local vector storage
- `API_PORT`: Port for the REST API
- `LOG_LEVEL`: Logging verbosity (DEBUG, INFO, WARNING, ERROR)
- `VECTOR_STORE_TYPE`: Choose between "chroma" or "pinecone"

### Resource Allocation

Adjust resources in `k8s/overlays/production/deployment-patch.yaml`:

```yaml
resources:
  requests:
    memory: "8Gi"
    cpu: "4"
  limits:
    memory: "16Gi"
    cpu: "8"
```

### GPU Configuration

The Ollama deployment is configured to use NVIDIA A100 GPUs. Modify the node selector in `k8s/base/ollama-deployment.yaml` if using different GPU types:

```yaml
nodeSelector:
  nvidia.com/gpu.product: NVIDIA-A100-SXM4-80GB
```

## API Usage

Once deployed, the API is accessible at the LoadBalancer endpoint:

```bash
# Get the API endpoint
API_ENDPOINT=$(kubectl get svc client-tracker-api-service -n client-tracker -o jsonpath='{.status.loadBalancer.ingress[0].ip}')

# Health check
curl http://$API_ENDPOINT/health

# Query the assistant
curl -X POST http://$API_ENDPOINT/api/v1/query \
  -H "Content-Type: application/json" \
  -d '{
    "question": "What is the status of Meria onboarding?",
    "max_context_length": 1000
  }'
```

## Monitoring

### View Logs

```bash
# API logs
kubectl logs -f deployment/client-tracker-api -n client-tracker

# Ollama logs
kubectl logs -f deployment/ollama -n client-tracker
```

### Metrics

Access metrics endpoint:

```bash
curl http://$API_ENDPOINT/metrics
```

### ArgoCD Dashboard

Monitor deployment status in ArgoCD:

```bash
# Port-forward ArgoCD server
kubectl port-forward svc/argocd-server -n argocd 8080:443

# Access at https://localhost:8080
```

## Troubleshooting

### Common Issues

1. **Pods stuck in Pending state**
   - Check GPU node availability: `kubectl describe nodes | grep nvidia`
   - Verify GPU resource requests: `kubectl describe pod <pod-name> -n client-tracker`

2. **Model loading failures**
   - Check Ollama connectivity: `kubectl exec -it deployment/ollama -n client-tracker -- curl http://localhost:11434`
   - Verify model cache volume: `kubectl describe pvc model-cache-pvc -n client-tracker`

3. **API not responding**
   - Check readiness probe: `kubectl describe pod <api-pod> -n client-tracker`
   - Review API logs: `kubectl logs <api-pod> -n client-tracker`

### Debug Commands

```bash
# Get detailed pod information
kubectl describe pod -l app=client-tracker-api -n client-tracker

# Check events
kubectl get events -n client-tracker --sort-by='.lastTimestamp'

# Test internal connectivity
kubectl run -it --rm debug --image=curlimages/curl --restart=Never -n client-tracker -- sh
# Inside the debug pod:
curl http://ollama-service:11434
curl http://client-tracker-api-service:8080/health
```

## Scaling

### Horizontal Scaling

Adjust the number of API replicas:

```bash
kubectl scale deployment client-tracker-api --replicas=5 -n client-tracker
```

Or configure HPA (Horizontal Pod Autoscaler):

```yaml
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: client-tracker-api-hpa
  namespace: client-tracker
spec:
  scaleTargetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: client-tracker-api
  minReplicas: 3
  maxReplicas: 10
  metrics:
  - type: Resource
    resource:
      name: cpu
      target:
        type: Utilization
        averageUtilization: 70
```

### Vertical Scaling

For GPU resources, modify the Ollama deployment:

```bash
kubectl edit deployment ollama -n client-tracker
# Adjust nvidia.com/gpu limits
```

## Backup and Recovery

### Vector Store Backup

For Pinecone:
- Backups are handled automatically by Pinecone
- Configure collection backups in Pinecone console

For ChromaDB (local):
```bash
# Create backup
kubectl exec deployment/client-tracker-api -n client-tracker -- tar -czf /tmp/chroma-backup.tar.gz /data/chroma_db_clients

# Copy backup locally
kubectl cp client-tracker/<pod-name>:/tmp/chroma-backup.tar.gz ./chroma-backup.tar.gz
```

### Application State

ArgoCD maintains Git history for easy rollbacks:

```bash
# List revisions
argocd app history client-tracker

# Rollback to previous version
argocd app rollback client-tracker <revision>
```

## Security Considerations

1. **Network Policies**: Restrict traffic between pods
2. **RBAC**: Use service accounts with minimal permissions
3. **Secrets Management**: Use sealed-secrets or external secret managers
4. **Image Scanning**: Enable vulnerability scanning in GHCR
5. **Pod Security Standards**: Enforce security contexts

## Cost Optimization

1. **GPU Sharing**: Consider using GPU virtualization for development environments
2. **Spot Instances**: Use spot/preemptible nodes for non-critical workloads
3. **Model Caching**: Ensure model cache volume is properly sized to avoid re-downloads
4. **Request Limits**: Set appropriate resource requests to avoid over-provisioning

## Support

For issues or questions:
- Check logs and events first
- Review the [troubleshooting guide](#troubleshooting)
- Open an issue in the GitHub repository
- Contact the platform team for infrastructure issues