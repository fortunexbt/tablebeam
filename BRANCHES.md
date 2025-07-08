# 📌 Branch Overview

This repository has multiple branches for different use cases:

## 🌿 Branches

### 1. `main` - Validator/Client Tracker
The original implementation focused on tracking institutional validators and client onboarding.
- **Use case**: Specific to validator/client management
- **Required columns**: Client, Type, Account, Communication Channel, etc.
- **Best for**: Teams managing validator relationships

### 2. `generic-spreadsheet-qa` - Universal Spreadsheet Q&A
A flexible version that works with ANY spreadsheet or CSV file.
- **Use case**: Any tabular data (customers, inventory, finances, etc.)
- **Required columns**: None! Adapts to your data structure
- **Best for**: General purpose data analysis

### 3. `cloud-infrastructure` - Kubernetes Deployment
Production-ready cloud deployment with REST API.
- **Use case**: Team-wide API access without local setup
- **Features**: GPU support, auto-scaling, Pinecone integration
- **Best for**: Enterprise deployments

## 🔄 Switching Branches

```bash
# View all branches
git branch -a

# Switch to generic spreadsheet version
git checkout generic-spreadsheet-qa

# Switch to cloud deployment
git checkout cloud-infrastructure

# Go back to main
git checkout main
```

## 🎯 Which Branch Should I Use?

| Your Need | Branch | Why |
|-----------|--------|-----|
| Track validators/clients specifically | `main` | Optimized prompts and structure |
| Analyze any spreadsheet | `generic-spreadsheet-qa` | Works with any columns |
| Deploy to cloud/K8s | `cloud-infrastructure` | REST API, scalable |
| Local development | `main` or `generic-spreadsheet-qa` | Simple setup |

## 🔀 Merging Features

Features from different branches can be cherry-picked:

```bash
# Example: Add Google Sheets support to generic branch
git checkout generic-spreadsheet-qa
git cherry-pick <commit-hash-from-main>
```