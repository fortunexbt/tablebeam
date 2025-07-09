# ☁️ Client Tracker Assistant - Cloud Infrastructure Branch

This branch contains the cloud-native version of the Client Tracker Assistant, designed for production deployment on Kubernetes with GPU support.

## 🎯 Purpose

While the `main` branch provides a local development experience with Ollama, this `cloud-infrastructure` branch is designed for:

- **Production deployment** on Kubernetes clusters
- **Shared team access** via REST API
- **GPU acceleration** with NVIDIA A100s
- **Scalable architecture** with auto-scaling
- **No local setup required** for end users

## 🏗️ Architecture Differences

| Feature | Main Branch (Local) | Cloud-Infrastructure Branch |
|---------|-------------------|---------------------------|
| Deployment | Local machine | Kubernetes cluster |
| LLM Runtime | Local Ollama | Containerized Ollama on GPU |
| Vector Store | Local ChromaDB | Pinecone (cloud) or ChromaDB |
| Interface | CLI only | REST API + CLI |
| Scaling | Single instance | Multi-replica with auto-scaling |
| GPU | Optional | Required (A100 recommended) |
| Setup Time | ~10 minutes | ~30 minutes (one-time) |

## 🚀 Quick Start

### For End Users (Using the API)

Once deployed by your infrastructure team:

```bash
# No local setup required! Just use the API:
curl -X POST https://api.your-domain.com/api/v1/query \
  -H "Content-Type: application/json" \
  -d '{"question": "What is the status of Meria onboarding?"}'
```

### For Infrastructure Teams (Deployment)

1. **Prerequisites**:
   - Kubernetes cluster with GPU nodes
   - ArgoCD installed
   - Pinecone account (optional)

2. **Deploy**:
   ```bash
   # Configure secrets
   kubectl create secret generic client-tracker-secrets \
     --from-literal=pinecone-api-key=YOUR_KEY \
     -n client-tracker

   # Deploy with ArgoCD
   kubectl apply -f argocd/application.yaml
   ```

3. **Verify**:
   ```bash
   kubectl get pods -n client-tracker
   ```

## 📁 Branch Structure

This branch includes additional files not present in `main`:

```
.
├── Dockerfile                    # Container definition
├── .github/workflows/            # CI/CD pipeline
├── k8s/                         # Kubernetes manifests
│   ├── base/                    # Base configurations
│   └── overlays/production/     # Production overrides
├── argocd/                      # GitOps deployment
├── src/
│   ├── api_server.py           # REST API (new)
│   ├── pinecone_vector.py      # Cloud vector store (new)
│   └── migrate_to_pinecone.py  # Migration tool (new)
├── docs/
│   └── pinecone_integration.md # Cloud vector store docs
├── DEPLOYMENT.md               # Cloud deployment guide
└── README_CLOUD.md            # This file
```

## 🔄 Syncing with Main Branch

To incorporate updates from the main branch:

```bash
# Fetch latest changes
git fetch origin main

# Merge main into cloud-infrastructure
git checkout cloud-infrastructure
git merge origin/main

# Resolve any conflicts in:
# - src/vector.py (supports both ChromaDB and Pinecone)
# - src/requirements.txt (includes cloud dependencies)
```

## 🤝 Development Workflow

1. **Local Development**: Use `main` branch
2. **Test Changes**: Develop and test locally
3. **Cloud Deployment**: Cherry-pick or merge changes to `cloud-infrastructure`
4. **Production**: Deploy via ArgoCD from this branch

## 📊 Choosing Vector Stores

| Use Case | Recommended | Why |
|----------|-------------|-----|
| Local Development | ChromaDB | No external dependencies |
| Cloud Production | Pinecone | Managed, scalable, no persistence needed |
| Hybrid | Both | ChromaDB for dev, Pinecone for prod |

## 🔐 Security Notes

- API keys and secrets are managed via Kubernetes secrets
- Network policies restrict pod-to-pod communication
- API authentication can be added as needed
- All containers run as non-root users

## 📚 Documentation

- **Local Setup**: See [README.md](https://github.com/your-org/client-tracker-assistant/blob/main/README.md) in main branch
- **Cloud Deployment**: See [DEPLOYMENT.md](DEPLOYMENT.md) in this branch
- **API Reference**: See [src/API_README.md](src/API_README.md)
- **Architecture**: See [UPGRADE_SUMMARY.md](UPGRADE_SUMMARY.md)

## 🏷️ Branch Strategy

- `main`: Stable local development version
- `cloud-infrastructure`: Production cloud deployment
- Feature branches: Create from `main`, test locally, then adapt for cloud

This separation ensures that:
1. Local development remains simple and accessible
2. Cloud infrastructure can evolve independently
3. Teams can choose the deployment model that fits their needs