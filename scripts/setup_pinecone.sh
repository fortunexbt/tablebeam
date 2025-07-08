#!/bin/bash
# Setup script for Pinecone integration in client-tracker-assistant

set -e

echo "================================"
echo "Pinecone Setup for Client Tracker"
echo "================================"
echo

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Check if .env file exists
if [ -f .env ]; then
    echo -e "${YELLOW}Found existing .env file${NC}"
    read -p "Do you want to backup the existing .env file? (y/n): " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        cp .env .env.backup.$(date +%Y%m%d_%H%M%S)
        echo -e "${GREEN}Backup created${NC}"
    fi
else
    # Create .env from example
    if [ -f .env.example ]; then
        cp .env.example .env
        echo -e "${GREEN}Created .env file from .env.example${NC}"
    else
        echo -e "${RED}Error: .env.example not found${NC}"
        exit 1
    fi
fi

# Check for Pinecone API key
echo
echo "Checking for Pinecone API key..."
if [ -z "$PINECONE_API_KEY" ]; then
    echo -e "${YELLOW}PINECONE_API_KEY not found in environment${NC}"
    read -p "Enter your Pinecone API key: " api_key
    
    # Update .env file
    if grep -q "PINECONE_API_KEY=" .env; then
        sed -i.bak "s/PINECONE_API_KEY=.*/PINECONE_API_KEY=$api_key/" .env
    else
        echo "PINECONE_API_KEY=$api_key" >> .env
    fi
    
    export PINECONE_API_KEY=$api_key
    echo -e "${GREEN}API key saved to .env file${NC}"
else
    echo -e "${GREEN}Using existing PINECONE_API_KEY from environment${NC}"
fi

# Ask about vector store preference
echo
read -p "Do you want to use Pinecone as the default vector store? (y/n): " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    sed -i.bak "s/VECTOR_STORE_TYPE=.*/VECTOR_STORE_TYPE=pinecone/" .env
    echo -e "${GREEN}Set Pinecone as default vector store${NC}"
else
    echo -e "${YELLOW}Keeping current vector store setting${NC}"
fi

# Ask about namespace
echo
read -p "Do you want to set a custom namespace? (default: none) [y/n]: " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    read -p "Enter namespace name: " namespace
    if grep -q "PINECONE_NAMESPACE=" .env; then
        sed -i.bak "s/PINECONE_NAMESPACE=.*/PINECONE_NAMESPACE=$namespace/" .env
    else
        echo "PINECONE_NAMESPACE=$namespace" >> .env
    fi
    echo -e "${GREEN}Namespace set to: $namespace${NC}"
fi

# Install dependencies
echo
echo "Installing Python dependencies..."
if [ -f src/requirements.txt ]; then
    pip install -r src/requirements.txt
    echo -e "${GREEN}Dependencies installed${NC}"
else
    echo -e "${RED}Error: src/requirements.txt not found${NC}"
    exit 1
fi

# Offer to run migration
echo
echo "Setup complete!"
echo
read -p "Do you want to migrate existing ChromaDB data to Pinecone? (y/n): " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    echo "Running migration in dry-run mode first..."
    python src/migrate_to_pinecone.py --dry-run
    
    echo
    read -p "Proceed with actual migration? (y/n): " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        python src/migrate_to_pinecone.py --output-report migration_report.json
        echo -e "${GREEN}Migration complete! Report saved to migration_report.json${NC}"
    fi
fi

# Final instructions
echo
echo -e "${GREEN}================================${NC}"
echo -e "${GREEN}Setup Complete!${NC}"
echo -e "${GREEN}================================${NC}"
echo
echo "Next steps:"
echo "1. Review your .env file to ensure settings are correct"
echo "2. Test the integration with: python examples/pinecone_example.py"
echo "3. Check the documentation at docs/pinecone_integration.md"
echo
echo "To use Pinecone in your code:"
echo "  from src.vector import get_retriever"
echo "  retriever = get_retriever('client_tracking.csv')"
echo