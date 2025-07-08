# Pinecone Integration Guide

This guide explains how to use Pinecone as an alternative vector store to ChromaDB in the client-tracker-assistant.

## Overview

The client-tracker-assistant now supports Pinecone as a high-performance, cloud-based vector database alternative to ChromaDB. Pinecone offers:

- **Serverless architecture**: No infrastructure to manage
- **Integrated embeddings**: Built-in llama-text-embed-v2 model
- **Multi-tenancy**: Namespace support for data isolation
- **Production-ready**: Automatic scaling and high availability
- **Advanced features**: Metadata filtering, hybrid search, and reranking

## Setup

### 1. Prerequisites

- Python 3.8+
- Pinecone account (sign up at https://www.pinecone.io)
- Pinecone API key

### 2. Installation

Install the required dependencies:

```bash
pip install -r src/requirements.txt
```

### 3. Configuration

Create a `.env` file based on `.env.example`:

```bash
cp .env.example .env
```

Edit `.env` and configure Pinecone:

```env
# Use Pinecone instead of ChromaDB
VECTOR_STORE_TYPE=pinecone

# Your Pinecone API key
PINECONE_API_KEY=your-api-key-here

# Optional: Custom index name (default: client-tracker)
PINECONE_INDEX_NAME=client-tracker

# Optional: Namespace for multi-tenancy
PINECONE_NAMESPACE=production
```

## Usage

### Using Pinecone in Your Application

The vector store abstraction allows seamless switching between ChromaDB and Pinecone:

```python
from src.vector import get_retriever

# Automatically uses Pinecone if VECTOR_STORE_TYPE=pinecone
retriever = get_retriever("client_tracking.csv")

# Or explicitly specify Pinecone
retriever = get_retriever(
    "client_tracking.csv",
    vector_store_type="pinecone",
    namespace="production"
)

# Use the retriever as normal
results = retriever.get_relevant_documents("Find clients using Slack")
```

### Direct Pinecone Usage

For advanced use cases, you can use the Pinecone integration directly:

```python
from src.pinecone_vector import PineconeConfig, PineconeVectorStore

# Configure Pinecone
config = PineconeConfig(
    api_key="your-api-key",
    index_name="client-tracker",
    namespace="production"
)

# Create vector store
vector_store = PineconeVectorStore(config)

# Search with metadata filtering
results = vector_store.search(
    query="enterprise clients",
    top_k=10,
    filter={"size": "Enterprise"}
)

# Rerank results
reranked = vector_store.rerank(
    query="enterprise clients",
    matches=results,
    top_k=5
)
```

## Migration from ChromaDB

### Automated Migration

Use the provided migration script to transfer your data from ChromaDB to Pinecone:

```bash
# Basic migration
python src/migrate_to_pinecone.py

# Migration with custom settings
python src/migrate_to_pinecone.py \
    --chroma-path ./chroma_db_clients \
    --pinecone-index client-tracker \
    --pinecone-namespace production \
    --batch-size 100

# Dry run to preview migration
python src/migrate_to_pinecone.py --dry-run

# Save migration report
python src/migrate_to_pinecone.py --output-report migration_report.json
```

### Migration Options

- `--chroma-path`: Path to ChromaDB data (default: ./chroma_db_clients)
- `--chroma-collection`: ChromaDB collection name (default: client_tracking)
- `--pinecone-api-key`: Pinecone API key (or use env var)
- `--pinecone-index`: Target Pinecone index name
- `--pinecone-namespace`: Optional namespace for organization
- `--batch-size`: Documents per batch (default: 100)
- `--dry-run`: Simulate migration without uploading
- `--output-report`: Save detailed migration report

### Migration Process

1. **Extract**: Reads all documents from ChromaDB
2. **Transform**: Converts documents to Pinecone format
3. **Load**: Uploads documents in batches with retry logic
4. **Validate**: Verifies document count and performs sample searches

## Best Practices

### 1. Index Configuration

The Pinecone integration automatically creates indexes with optimal settings:

- **Dimension**: 1024 (for mxbai-embed-large)
- **Metric**: Cosine similarity
- **Serverless**: AWS us-east-1 by default

### 2. Batch Operations

Always use batch operations for better performance:

```python
# Good: Batch upsert
vector_store.upsert_documents(documents, show_progress=True)

# Configure batch size based on document size
config.batch_size = 100  # Default
```

### 3. Error Handling

The integration includes automatic retry logic with exponential backoff:

```python
@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
def upsert_documents(self, documents):
    # Automatic retry on failure
```

### 4. Namespace Strategy

Use namespaces for data isolation:

- `production`: Live client data
- `staging`: Test data
- `development`: Development data
- Per-client namespaces for multi-tenancy

### 5. Monitoring

Monitor your Pinecone usage:

```python
# Get index statistics
stats = vector_store.get_stats()
print(f"Total vectors: {stats['total_vectors']}")
print(f"Namespaces: {stats['namespaces']}")
```

## Performance Considerations

### ChromaDB vs Pinecone

| Feature | ChromaDB | Pinecone |
|---------|----------|----------|
| Deployment | Local/Self-hosted | Cloud/Serverless |
| Scaling | Manual | Automatic |
| Maintenance | Required | Managed |
| Cost | Infrastructure only | Usage-based |
| Performance | Good for small datasets | Optimized for scale |
| Persistence | Local disk | Cloud storage |

### When to Use Pinecone

- Production deployments requiring high availability
- Large datasets (>100k documents)
- Multi-tenant applications
- Global distribution requirements
- Minimal operational overhead

### When to Use ChromaDB

- Local development
- Small datasets (<10k documents)
- On-premise requirements
- Cost-sensitive applications
- Full control over data

## Troubleshooting

### Common Issues

1. **API Key Error**
   ```
   ValueError: Pinecone API key not provided
   ```
   Solution: Set `PINECONE_API_KEY` in your environment or `.env` file

2. **Index Not Found**
   ```
   IndexNotFoundError: Index 'client-tracker' not found
   ```
   Solution: The integration automatically creates indexes. Check your API key permissions.

3. **Dimension Mismatch**
   ```
   ValueError: Dimension mismatch
   ```
   Solution: Ensure you're using consistent embedding models. The default is 1024 dimensions for mxbai-embed-large.

4. **Rate Limiting**
   ```
   RateLimitError: Too many requests
   ```
   Solution: The integration includes automatic retry. For high volume, contact Pinecone support.

### Debug Mode

Enable debug logging for troubleshooting:

```python
import logging
logging.basicConfig(level=logging.DEBUG)
```

## Security Considerations

1. **API Key Management**
   - Never commit API keys to version control
   - Use environment variables or secure key management
   - Rotate keys regularly

2. **Data Privacy**
   - Use namespaces to isolate sensitive data
   - Enable encryption at rest (automatic in Pinecone)
   - Consider data residency requirements

3. **Access Control**
   - Use separate API keys for different environments
   - Implement application-level access control
   - Monitor API usage for anomalies

## Additional Resources

- [Pinecone Documentation](https://docs.pinecone.io)
- [Pinecone Python Client](https://github.com/pinecone-io/pinecone-python-client)
- [Vector Database Comparison](https://docs.pinecone.io/guides/get-started/vector-database-comparison)
- [Embedding Models Guide](https://docs.pinecone.io/models/overview)