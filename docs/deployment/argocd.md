# ArgoCD Configuration for Client Tracker Assistant

This directory contains the ArgoCD application manifests for deploying the Client Tracker Assistant to Kubernetes.

## Files

- `application.yaml` - Main ArgoCD Application manifest
- `appproject.yaml` - ArgoCD AppProject for access control and organization
- `values-production.yaml` - Production-specific configuration values
- `health-config.yaml` - Custom health check configurations

## Deployment Instructions

### Prerequisites

1. ArgoCD installed in your Kubernetes cluster
2. Access to the ArgoCD UI or CLI
3. Kubernetes cluster with appropriate permissions
4. GitHub repository access configured in ArgoCD

### Deploy Using ArgoCD CLI

1. First, create the AppProject (optional but recommended):
   ```bash
   kubectl apply -f appproject.yaml
   ```

2. Apply the health check configuration:
   ```bash
   kubectl apply -f health-config.yaml
   ```

3. Create the ArgoCD application:
   ```bash
   kubectl apply -f application.yaml
   ```

4. Alternatively, use the ArgoCD CLI:
   ```bash
   argocd app create -f application.yaml
   ```

### Deploy Using ArgoCD UI

1. Log into the ArgoCD UI
2. Click "New App"
3. Use the values from `application.yaml` to fill in the form
4. Click "Create"

## Configuration

### Sync Policy

The application is configured with:
- **Auto-sync**: Enabled with self-healing
- **Pruning**: Enabled to remove obsolete resources
- **Retry**: Configured with exponential backoff (max 5 retries)

### Health Checks

Custom health checks are configured for:
- Deployments: Check for progress deadline and replica availability
- PVCs: Ensure volumes are bound
- Services: Check LoadBalancer assignment

### Rollback

To rollback to a previous version:

```bash
# List application history
argocd app history client-tracker-assistant

# Rollback to a specific revision
argocd app rollback client-tracker-assistant <revision>
```

### Manual Sync

If auto-sync is disabled or you need to manually sync:

```bash
# Sync the application
argocd app sync client-tracker-assistant

# Sync with pruning
argocd app sync client-tracker-assistant --prune
```

## Monitoring

The application includes:
- Service monitoring endpoints at `/metrics`
- Health check endpoints at `/health`
- Configured alerts and dashboards (when monitoring is enabled)

## Security

- RBAC is configured through the AppProject
- Network policies restrict traffic
- Pod security contexts enforce non-root users
- TLS is enforced for all ingress traffic

## Troubleshooting

### Check Application Status
```bash
argocd app get client-tracker-assistant
```

### View Application Logs
```bash
argocd app logs client-tracker-assistant --follow
```

### Force Refresh
```bash
argocd app get client-tracker-assistant --refresh
```

### Debug Sync Issues
```bash
argocd app diff client-tracker-assistant
```

## Environment-Specific Overrides

The `values-production.yaml` file contains production-specific configurations including:
- Resource limits and requests
- Replica counts
- Ingress configuration
- Persistence settings
- Security policies

To use these values with Kustomize, reference them in your `kustomization.yaml` or create patches based on these values.