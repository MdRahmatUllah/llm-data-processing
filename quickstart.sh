#!/bin/bash
# Quick Start Script for Synthetic SFT Dataset Generation Pipeline
# This script runs the complete pipeline on the sample project

set -e  # Exit on error

echo "=========================================="
echo "Synthetic SFT Dataset Generation Pipeline"
echo "Quick Start Script"
echo "=========================================="
echo ""

# Colors for output
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Check if Python is installed
if ! command -v python &> /dev/null; then
    echo -e "${YELLOW}Error: Python is not installed${NC}"
    exit 1
fi

echo -e "${BLUE}Step 1: Installing dependencies...${NC}"
pip install -e . || {
    echo -e "${YELLOW}Warning: Installation failed. Trying manual install...${NC}"
    pip install pyyaml jsonschema jinja2 tiktoken sentencepiece openai httpx tenacity python-dotenv tqdm click
}
echo -e "${GREEN}✓ Dependencies installed${NC}"
echo ""

# Check if .env exists
if [ ! -f .env ]; then
    echo -e "${YELLOW}Warning: .env file not found. Creating default .env for Ollama...${NC}"
    cat > .env << EOF
# API Configuration for Ollama
API_BASE=http://localhost:11434/v1
API_KEY=ollama
API_TIMEOUT=1200
EOF
    echo -e "${GREEN}✓ Created .env file${NC}"
fi
echo ""

# Check if Ollama is running (optional)
echo -e "${BLUE}Checking Ollama connection...${NC}"
if command -v ollama &> /dev/null; then
    if ollama ps &> /dev/null; then
        echo -e "${GREEN}✓ Ollama is running${NC}"
        echo "Available models:"
        ollama list
    else
        echo -e "${YELLOW}Warning: Ollama is not running. Please start Ollama first.${NC}"
        echo "Run: ollama serve"
        exit 1
    fi
else
    echo -e "${YELLOW}Warning: Ollama not found. Make sure your LLM provider is configured in .env${NC}"
fi
echo ""

# Create necessary directories
echo -e "${BLUE}Step 2: Creating directories...${NC}"
mkdir -p workspace/chunks
mkdir -p workspace/verified
mkdir -p workspace/rejected
mkdir -p workspace/logs
mkdir -p output
echo -e "${GREEN}✓ Directories created${NC}"
echo ""

# Step 1: Chunking
echo -e "${BLUE}Step 3: Chunking sample markdown file...${NC}"
python -m src.script1_chunk_md \
  --input-root ./input \
  --project sample_project \
  --workspace ./workspace \
  --config ./config/app.config.yaml \
  --verbose

echo -e "${GREEN}✓ Chunking complete${NC}"
echo ""

# Show chunk statistics
CHUNK_COUNT=$(find workspace/chunks/sample_project -name "*.jsonl" -exec wc -l {} + | tail -1 | awk '{print $1}')
echo "Generated $CHUNK_COUNT chunks"
echo ""

# Step 2: Generation & Verification
echo -e "${BLUE}Step 4: Generating and verifying Q&A pairs...${NC}"
echo "This may take 1-2 hours with Ollama (20B model)"
echo "Press Ctrl+C to cancel, or wait for completion..."
echo ""

python -m src.script2_generate_verify \
  --workspace ./workspace \
  --config ./config/app.config.yaml \
  --parallel 1 \
  --verbose

echo -e "${GREEN}✓ Generation and verification complete${NC}"
echo ""

# Show generation statistics
VERIFIED_COUNT=$(find workspace/verified/sample_project -name "*.jsonl" -exec wc -l {} + 2>/dev/null | tail -1 | awk '{print $1}' || echo "0")
REJECTED_COUNT=$(find workspace/rejected/sample_project -name "*.jsonl" -exec wc -l {} + 2>/dev/null | tail -1 | awk '{print $1}' || echo "0")
echo "Verified items: $VERIFIED_COUNT"
echo "Rejected items: $REJECTED_COUNT"
echo ""

# Step 3: Packing
echo -e "${BLUE}Step 5: Packing into final datasets...${NC}"
python -m src.script3_pack_json \
  --workspace ./workspace \
  --output ./output \
  --config ./config/app.config.yaml \
  --seed 42 \
  --verbose

echo -e "${GREEN}✓ Packing complete${NC}"
echo ""

# Show final statistics
echo "=========================================="
echo -e "${GREEN}Pipeline Complete!${NC}"
echo "=========================================="
echo ""
echo "Output files:"
ls -lh output/
echo ""
echo "Next steps:"
echo "1. Review the generated datasets in output/"
echo "2. Check logs in workspace/logs/ for details"
echo "3. Use the datasets for fine-tuning your model"
echo ""
echo "For more information, see README.md"

