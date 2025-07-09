# Local vs Cloud Deployment Guide

This guide helps you choose between local and cloud deployment modes for the Spreadsheet Q&A Assistant.

## Deployment Modes Overview

### Local Mode
- Runs entirely on your machine
- Uses Ollama for LLM inference
- Stores vectors in ChromaDB locally
- Accessed via terminal interface

### Cloud Mode
- Runs as API server (FastAPI)
- Can be deployed to Kubernetes
- Supports Pinecone for scalable vector storage
- Accessed via REST API

## Comparison Table

| Feature | Local Mode | Cloud Mode |
|---------|------------|------------|
| **Setup Complexity** | Simple | Complex |
| **Privacy** | Complete - all data stays local | Depends on deployment |
| **Scalability** | Single user | Multi-user |
| **Performance** | Depends on local hardware | Scalable resources |
| **Cost** | Free (uses local resources) | Infrastructure costs |
| **Access Method** | Terminal CLI | REST API |
| **Vector Storage** | ChromaDB (local) | ChromaDB or Pinecone |
| **GPU Support** | Local GPU only | Cloud GPU options |

## When to Use Local Mode

Choose local mode when you:

- Work with sensitive/confidential data
- Need a simple, quick setup
- Are the only user
- Want zero infrastructure costs
- Have sufficient local compute resources
- Prefer terminal/CLI interfaces

### Local Mode Setup
```bash
# Install and run
pip install -r src/requirements.txt
python src/chat_interface.py
```

## When to Use Cloud Mode

Choose cloud mode when you:

- Need to serve multiple users
- Want API access for integrations
- Require high availability
- Need scalable compute resources
- Building a production application
- Want centralized vector storage

### Cloud Mode Setup
```bash
# Basic API server
python src/api_server.py

# Docker deployment
docker build -t spreadsheet-qa .
docker run -p 8000:8000 spreadsheet-qa

# Kubernetes deployment
kubectl apply -k k8s/overlays/production/
```

## Feature Availability by Mode

### Local Mode Only
- Terminal color highlighting
- Interactive prompts
- Direct file system access

### Cloud Mode Only
- REST API endpoints
- Concurrent request handling
- Kubernetes scaling
- Pinecone integration
- Health checks and monitoring

### Both Modes
- Google Sheets support
- CSV file processing
- Ollama LLM integration
- ChromaDB storage option
- Same Q&A capabilities

## Migration Between Modes

### Local to Cloud
1. Export your data source list
2. Deploy cloud infrastructure
3. Load data via API
4. Update client applications to use API

### Cloud to Local
1. Export data from cloud storage
2. Install local dependencies
3. Run local chat interface
4. Point to same data sources

## Security Considerations

### Local Mode
- All data remains on your machine
- No network exposure
- Direct file system access
- User-level permissions only

### Cloud Mode
- Requires authentication setup
- Network security needed
- API rate limiting recommended
- Encryption in transit important

## Performance Tips

### Local Mode
- Use SSD for ChromaDB storage
- Ensure adequate RAM (8GB+)
- GPU recommended for faster embeddings
- Close other applications

### Cloud Mode
- Use GPU nodes for LLM
- Scale API replicas for load
- Consider Pinecone for large datasets
- Use caching strategies

## Cost Analysis

### Local Mode Costs
- Hardware (one-time)
- Electricity
- No ongoing fees

### Cloud Mode Costs
- Compute instances
- Storage (ChromaDB or Pinecone)
- Network egress
- GPU instances (if used)
- Monitoring/logging

## Decision Flow Chart

```
Start
  ↓
Multiple users? → Yes → Cloud Mode
  ↓ No
Sensitive data? → Yes → Local Mode
  ↓ No
Need API? → Yes → Cloud Mode
  ↓ No
Budget constraints? → Yes → Local Mode
  ↓ No
High availability? → Yes → Cloud Mode
  ↓ No
Local Mode (Default)
```

## Next Steps

- **For Local Mode**: See [Installation Guide](installation.md)
- **For Cloud Mode**: See [Kubernetes Deployment](../deployment/kubernetes.md)