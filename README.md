# Synthetic SFT Dataset Generation Pipeline

A comprehensive, production-ready pipeline for generating high-quality synthetic Supervised Fine-Tuning (SFT) datasets from markdown documents using Large Language Models.

## 📋 Table of Contents

- [Overview](#overview)
- [Features](#features)
- [Architecture](#architecture)
- [Prerequisites](#prerequisites)
- [Installation](#installation)
- [Quick Start](#quick-start)
- [Configuration](#configuration)
- [Usage Guide](#usage-guide)
- [Output Format](#output-format)
- [Troubleshooting](#troubleshooting)
- [Advanced Topics](#advanced-topics)
- [Contributing](#contributing)

---

## 🎯 Overview

This pipeline transforms markdown documentation into synthetic question-answer pairs suitable for fine-tuning language models. It uses a three-stage process:

1. **Chunking** - Split markdown files into semantically meaningful, overlapping chunks
2. **Generation & Verification** - Generate synthetic Q&A pairs and verify their quality
3. **Packing** - Organize verified items into train/test datasets with sharding

**Use Cases:**
- Creating training data for domain-specific language models
- Generating Q&A datasets from technical documentation
- Building instruction-following datasets
- Augmenting existing training data with synthetic examples

---

## ✨ Features

- ✅ **Semantic Chunking** - Intelligent splitting at section boundaries with configurable overlap
- ✅ **Multi-Model Support** - Works with OpenAI, Anthropic, Ollama, and any OpenAI-compatible API
- ✅ **Robust JSON Parsing** - Automatic error recovery for LLM-generated JSON
- ✅ **Quality Verification** - 12 comprehensive validation checks including special token verification
- ✅ **Rate Limiting** - Built-in rate limiting and retry logic with exponential backoff
- ✅ **Parallel Processing** - Configurable parallelism for faster generation
- ✅ **Comprehensive Logging** - Detailed logs and debug files for troubleshooting
- ✅ **Resume Support** - Continue from where you left off if interrupted
- ✅ **Flexible Configuration** - YAML-based configuration with environment variable support

---

## 🏗️ Architecture

```
┌─────────────────┐
│  Markdown Files │
│   (input/)      │
└────────┬────────┘
         │
         ▼
┌─────────────────────────────────────────┐
│  Script 1: Chunking (script1_chunk_md)  │
│  • Tokenize markdown                    │
│  • Split at semantic boundaries         │
│  • Add overlap for context              │
└────────┬────────────────────────────────┘
         │
         ▼
┌─────────────────────────────────────────┐
│  Chunks (workspace/chunks/*.jsonl)      │
└────────┬────────────────────────────────┘
         │
         ▼
┌──────────────────────────────────────────────┐
│  Script 2: Generation & Verification         │
│  (script2_generate_verify)                   │
│  • Generate Q&A pairs from chunks            │
│  • Verify with LLM + local checks            │
│  • Save verified/rejected items separately   │
└────────┬─────────────────────────────────────┘
         │
         ▼
┌──────────────────────────────────────────────┐
│  Verified Items (workspace/verified/*.jsonl) │
└────────┬─────────────────────────────────────┘
         │
         ▼
┌──────────────────────────────────────────────┐
│  Script 3: Packing (script3_pack_json)       │
│  • Split into train/test sets                │
│  • Shard large datasets                      │
│  • Generate manifest files                   │
└────────┬─────────────────────────────────────┘
         │
         ▼
┌──────────────────────────────────────────────┐
│  Final Datasets (output/train_*.jsonl,       │
│                  output/test_*.jsonl)        │
└──────────────────────────────────────────────┘
```

---

## 📦 Prerequisites

### System Requirements

- **Python**: 3.10 or higher
- **Memory**: 4GB+ RAM (8GB+ recommended for parallel processing)
- **Storage**: Varies by dataset size (estimate 10-100MB per 1000 items)

### LLM Provider (Choose One)

**Option 1: Ollama (Recommended for Local Development)**
- Install Ollama: https://ollama.ai/
- Pull required models:
  ```bash
  ollama pull gpt-oss:20b      # For generation
  ollama pull qwen3:8b          # For verification
  ```
- Verify Ollama is running: `ollama ps`

**Option 2: OpenAI API**
- OpenAI API key with GPT-4 or GPT-3.5 access
- Set `OPENAI_API_KEY` environment variable

**Option 3: Other Providers**
- Any OpenAI-compatible API endpoint
- Configure `API_BASE` and `API_KEY` in `.env`

---

## 🚀 Installation

### Quick Setup (Ubuntu/Linux)

**📖 For detailed Ubuntu setup with virtual environment, see [UBUNTU_SETUP.md](UBUNTU_SETUP.md)**

```bash
# Create virtual environment
python3 -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

### 1. Clone the Repository

```bash
git clone <repository-url>
cd data-processing
```

### 2. Install Dependencies

**Option 1: Using requirements.txt (Recommended)**
```bash
pip install -r requirements.txt
```

**Option 2: Using pip (editable install)**
```bash
pip install -e .
```

**Option 3: With development dependencies**
```bash
pip install -e ".[dev]"
```

**Option 4: Manual installation**
```bash
pip install pyyaml jsonschema jinja2 tiktoken sentencepiece openai httpx tenacity python-dotenv tqdm click
```

### 3. Set Up Environment Variables

Create a `.env` file in the project root:

```bash
# For Ollama (local)
API_BASE=http://localhost:11434/v1
API_KEY=ollama
API_TIMEOUT=1200

# For OpenAI
# API_BASE=https://api.openai.com/v1
# API_KEY=sk-your-api-key-here
# API_TIMEOUT=60
```

### 4. Verify Installation

```bash
# Test Ollama connection (if using Ollama)
python test_ollama_connection.py

# Test JSON parsing utilities
python test_json_parsing.py
```

---

## 🎬 Quick Start

### Process the Sample Dataset

The repository includes a sample markdown file to help you get started:

```bash
# Step 1: Chunk the sample markdown file
python -m src.script1_chunk_md \
  --input-root ./input \
  --project sample_project \
  --workspace ./workspace \
  --config ./config/app.config.yaml \
  --verbose

# Step 2: Generate and verify Q&A pairs
python -m src.script2_generate_verify \
  --workspace ./workspace \
  --config ./config/app.config.yaml \
  --parallel 1 \
  --verbose

# Step 3: Pack into final datasets
python -m src.script3_pack_json \
  --workspace ./workspace \
  --output ./output \
  --config ./config/app.config.yaml \
  --seed 42 \
  --verbose
```

### Expected Output

After running all three scripts, you should see:

```
workspace/
├── chunks/
│   └── sample_project/
│       └── introduction_to_algorithms.md.chunks.jsonl  # ~10-15 chunks
├── verified/
│   └── sample_project/
│       └── verified_items_*.jsonl                      # ~20-30 verified items
├── rejected/
│   └── sample_project/
│       └── rejected_items_*.jsonl                      # Items that failed verification
└── logs/
    ├── script1_*.log
    ├── script2_*.log
    └── script3_*.log

output/
├── train_shard_0.jsonl                                 # Training data
├── test_shard_0.jsonl                                  # Test data
└── manifest.json                                       # Dataset metadata
```

---

## ⚙️ Configuration

### Main Configuration File: `config/app.config.yaml`

```yaml
# Project metadata
project_name: "SyntheticDataset"
input_root: "./input"
workspace_root: "./workspace"
output_root: "./output"

# Chunking settings
chunking:
  tokenizer: "tiktoken:cl100k_base"  # or "sentencepiece:path/to/model"
  max_tokens_per_chunk: 1024
  overlap_tokens: 128
  semantic_breaks:
    heading_1: 1000    # Strong break at # headings
    heading_2: 500     # Medium break at ## headings
    heading_3: 200     # Weak break at ### headings
    code_block: 100    # Break at code blocks
    list_item: 50      # Break at list items

# Generation settings
generation:
  model_name: "gpt-oss:20b"          # Ollama model
  temperature: 0.7                    # Higher = more creative
  max_tokens: 4096                    # Max response length
  items_per_chunk: 2                  # Q&A pairs per chunk
  system_prompt_file: "./config/prompts/sft_system.txt"
  user_prompt_template: "./config/prompts/sft_user.jinja"

# Verification settings
verification:
  enabled: true
  model_name: "qwen3:8b"              # Smaller model for verification
  temperature: 0.0                    # Deterministic
  max_tokens: 4000
  system_prompt_file: "./config/prompts/sft_verifier_system.txt"
  user_prompt_template: "./config/prompts/sft_verifier_user.jinja"
  local_checks:
    - json_schema                     # Validate JSON structure
    - messages_shape                  # Check message format
    - special_tokens                  # Verify special tokens
    - boxed_answer                    # Check for \boxed{} answers

# Packing settings
packing:
  train_ratio: 0.9                    # 90% train, 10% test
  max_items_per_shard: 10000          # Shard size
  shuffle: true                       # Shuffle before splitting

# Runtime settings
runtime:
  max_requests_per_minute: 120        # Rate limiting
  max_tokens_per_minute: 200000
  parallel_chunks: 1                  # Parallelism (1 for Ollama)
  retry_max_attempts: 3
  retry_backoff_base: 2
  timeout_seconds: 600                # 10 minutes for local LLMs
```

### Environment Variables: `.env`

```bash
# API Configuration
API_BASE=http://localhost:11434/v1   # Ollama endpoint
API_KEY=ollama                        # API key (any value for Ollama)
API_TIMEOUT=1200                      # Timeout in seconds
```

### Prompt Customization

Prompts are located in `config/prompts/`:

- `sft_system.txt` - System prompt for generation
- `sft_user.jinja` - User prompt template for generation (Jinja2)
- `sft_verifier_system.txt` - System prompt for verification
- `sft_verifier_user.jinja` - User prompt template for verification (Jinja2)

**Example: Customizing Generation Prompt**

Edit `config/prompts/sft_user.jinja`:

```jinja
You are analyzing content from the project "{{ project }}".

Source file: {{ file_name }}
Chunk {{ chunk_index }} (ID: {{ chunk_id[:16] }})

Generate {{ n }} high-quality question-answer pairs based on the following content:

---
{{ chunk_text }}
---

Requirements:
1. Questions should be diverse and cover different aspects
2. Answers must include reasoning in <|begin_of_thought|>...<|end_of_thought|>
3. Final answers must be in <|begin_of_solution|>...<|end_of_solution|>
4. Use \boxed{} for final answers when appropriate

Output as JSON array: [{"problem": "...", "solution": "..."}]
```

---

## 📖 Usage Guide

### Script 1: Chunking Markdown Files

**Purpose:** Split markdown files into overlapping chunks for processing.

**Command:**
```bash
python -m src.script1_chunk_md \
  --input-root ./input \
  --project <project_name> \
  --workspace ./workspace \
  --config ./config/app.config.yaml \
  --verbose
```

**Arguments:**
- `--input-root`: Directory containing project folders with markdown files
- `--project`: (Optional) Specific project to process. If omitted, processes all projects
- `--workspace`: Output directory for chunks
- `--config`: Path to configuration file
- `--verbose`: Enable detailed logging

**Input Format:**
```
input/
└── my_project/
    ├── document1.md
    ├── document2.md
    └── subfolder/
        └── document3.md
```

**Output:**
```
workspace/chunks/my_project/
├── document1.md.chunks.jsonl
├── document2.md.chunks.jsonl
└── document3.md.chunks.jsonl
```

**Chunk Format (JSONL):**
```json
{
  "chunk_id": "sha256:abc123...",
  "project": "my_project",
  "file_name": "document1.md",
  "file_sha1": "def456...",
  "chunk_index": 0,
  "text": "# Chapter 1\n\nContent here...",
  "token_count": 512,
  "char_count": 2048,
  "start_line": 1,
  "end_line": 50,
  "created_at": "2025-11-07T12:00:00Z"
}
```

---

### Script 2: Generation & Verification

**Purpose:** Generate synthetic Q&A pairs from chunks and verify their quality.

**Command:**
```bash
python -m src.script2_generate_verify \
  --workspace ./workspace \
  --config ./config/app.config.yaml \
  --parallel 1 \
  --resume \
  --verbose
```

**Arguments:**
- `--workspace`: Workspace directory containing chunks
- `--config`: Path to configuration file
- `--parallel`: Number of chunks to process in parallel (default: from config)
- `--resume`: Skip already processed chunks
- `--verbose`: Enable detailed logging

**Processing Flow:**
1. Load chunks from `workspace/chunks/`
2. For each chunk:
   - Generate N items using generation model
   - Parse and sanitize JSON response
   - Run local validation checks
   - Verify with verification model (if enabled)
   - Save to `verified/` or `rejected/` based on results
3. Generate processing report

**Output:**
```
workspace/
├── verified/
│   └── my_project/
│       └── verified_items_20251107_120000.jsonl
├── rejected/
│   └── my_project/
│       └── rejected_items_20251107_120000.jsonl
└── logs/
    ├── script2_20251107_120000.log
    └── failed_json/                    # Debug files for JSON errors
        ├── chunk_abc123.txt
        └── verifier_def456.txt
```

**Verified Item Format (JSONL):**
```json
{
  "id": "uuid-1234-5678",
  "chunk_id": "sha256:abc123...",
  "project": "my_project",
  "messages": [
    {
      "role": "user",
      "content": "What is the time complexity of bubble sort?"
    },
    {
      "role": "assistant",
      "content": "<|begin_of_thought|>\nBubble sort compares adjacent elements...\n<|end_of_thought|>\n<|begin_of_solution|>\nThe time complexity is \\boxed{O(n^2)}\n<|end_of_solution|>"
    }
  ],
  "metadata": {
    "source_file": "document1.md",
    "chunk_index": 0,
    "difficulty": "medium",
    "topic": "algorithms"
  },
  "verification_report": {
    "passed": true,
    "errors": [],
    "checks": {
      "json_schema_valid": true,
      "messages_shape_valid": true,
      "has_thought_begin_token": true,
      "has_thought_end_token": true,
      "has_solution_begin_token": true,
      "has_solution_end_token": true,
      "thought_properly_paired": true,
      "solution_properly_paired": true,
      "thought_before_solution": true,
      "has_boxed_answer": true,
      "verifier_approved": true
    }
  },
  "created_at": "2025-11-07T12:00:00Z"
}
```

**Performance Tips:**
- **Local LLMs (Ollama)**: Use `--parallel 1` to avoid overwhelming the server
- **Cloud APIs**: Use `--parallel 4-8` for faster processing
- **Timeout Issues**: Increase `timeout_seconds` in config for slower models
- **JSON Errors**: Check `workspace/logs/failed_json/` for debug information

**Expected Runtime:**
- **Ollama (20B model)**: ~2-5 minutes per chunk (depends on hardware)
- **OpenAI GPT-4**: ~30-60 seconds per chunk
- **Total for 30 chunks**: 1-2.5 hours (Ollama), 15-30 minutes (OpenAI)

---

### Script 3: Packing into Final Datasets

**Purpose:** Organize verified items into train/test datasets with sharding.

**Command:**
```bash
python -m src.script3_pack_json \
  --workspace ./workspace \
  --output ./output \
  --config ./config/app.config.yaml \
  --seed 42 \
  --verbose
```

**Arguments:**
- `--workspace`: Workspace directory containing verified items
- `--output`: Output directory for final datasets
- `--config`: Path to configuration file
- `--seed`: Random seed for reproducible train/test splits
- `--verbose`: Enable detailed logging

**Processing Flow:**
1. Load all verified items from `workspace/verified/`
2. Shuffle items (if enabled)
3. Split into train/test sets based on `train_ratio`
4. Shard large datasets based on `max_items_per_shard`
5. Generate manifest file with dataset statistics

**Output:**
```
output/
├── train_shard_0.jsonl
├── train_shard_1.jsonl
├── test_shard_0.jsonl
└── manifest.json
```

**Manifest Format:**
```json
{
  "dataset_name": "SyntheticDataset",
  "created_at": "2025-11-07T12:00:00Z",
  "total_items": 1000,
  "train_items": 900,
  "test_items": 100,
  "train_shards": 1,
  "test_shards": 1,
  "train_ratio": 0.9,
  "seed": 42,
  "projects": ["my_project"],
  "shards": [
    {
      "name": "train_shard_0.jsonl",
      "split": "train",
      "items": 900,
      "size_bytes": 1234567
    },
    {
      "name": "test_shard_0.jsonl",
      "split": "test",
      "items": 100,
      "size_bytes": 123456
    }
  ]
}
```

**Final Dataset Format (JSONL):**

Each line is a training example in the standard chat format:

```json
{
  "messages": [
    {
      "role": "user",
      "content": "What is the time complexity of bubble sort?"
    },
    {
      "role": "assistant",
      "content": "<|begin_of_thought|>\nBubble sort compares adjacent elements repeatedly...\n<|end_of_thought|>\n<|begin_of_solution|>\nThe time complexity is \\boxed{O(n^2)}\n<|end_of_solution|>"
    }
  ]
}
```

---

## 📊 Output Format

### Special Tokens

The pipeline uses special tokens to structure the model's reasoning:

| Token | Purpose | Required |
|-------|---------|----------|
| `<\|begin_of_thought\|>` | Start of reasoning section | ✅ Yes |
| `<\|end_of_thought\|>` | End of reasoning section | ✅ Yes |
| `<\|begin_of_solution\|>` | Start of final answer | ✅ Yes |
| `<\|end_of_solution\|>` | End of final answer | ✅ Yes |

**Example Response:**
```
<|begin_of_thought|>
To find the time complexity, I need to analyze the nested loops.
The outer loop runs n times, and the inner loop also runs n times.
Therefore, the total number of comparisons is n × n = n².
<|end_of_thought|>

<|begin_of_solution|>
The time complexity of bubble sort is \boxed{O(n^2)} in the worst and average cases.
<|end_of_solution|>
```

### Validation Checks

The pipeline performs 12 comprehensive validation checks:

1. **json_schema_valid** - JSON structure matches schema
2. **messages_shape_valid** - Exactly 2 messages (user + assistant)
3. **has_thought_begin_token** - Contains `<|begin_of_thought|>`
4. **has_thought_end_token** - Contains `<|end_of_thought|>`
5. **has_solution_begin_token** - Contains `<|begin_of_solution|>`
6. **has_solution_end_token** - Contains `<|end_of_solution|>`
7. **thought_properly_paired** - Both thought tokens present or both absent
8. **solution_properly_paired** - Both solution tokens present or both absent
9. **thought_before_solution** - Thought section comes before solution
10. **has_boxed_answer** - Contains `\boxed{...}` for final answer
11. **verifier_approved** - LLM verifier approved the item
12. **overall_passed** - All checks passed

---

## 🔧 Troubleshooting

### Common Issues

#### 1. Timeout Errors

**Symptom:**
```
[ERROR] Request timeout (read): ReadTimeout. Current read timeout: 120s.
```

**Solutions:**

**Option A: Increase Timeout (Recommended)**
```yaml
# config/app.config.yaml
runtime:
  timeout_seconds: 600  # 10 minutes for local LLMs
```

**Option B: Reduce Parallelism**
```bash
python -m src.script2_generate_verify --parallel 1
```

**Option C: Use Smaller Model**
```yaml
# config/app.config.yaml
generation:
  model_name: "qwen3:8b"  # Smaller, faster model
```

---

#### 2. JSON Parsing Errors

**Symptom:**
```
[ERROR] Failed to parse JSON: Invalid \escape: line 4 column 123
```

**Solutions:**

The pipeline includes automatic JSON sanitization, but if errors persist:

**Step 1: Check Debug Files**
```bash
ls workspace/logs/failed_json/
cat workspace/logs/failed_json/chunk_abc123.txt
```

**Step 2: Review Sanitized JSON**

Debug files show:
- Raw LLM response
- Extracted JSON (after markdown removal)
- Sanitized JSON (after escape fixing)
- Error details

**Step 3: Improve Prompts**

If the model consistently generates invalid JSON, update prompts:

```jinja
# config/prompts/sft_user.jinja

CRITICAL: Output valid JSON only!
- Escape backslashes: "C:\Users" → "C:\\Users"
- No trailing commas
- Use double quotes for strings
```

**Step 4: Test JSON Parsing**
```bash
python test_json_parsing.py
```

---

#### 3. Verification Failures

**Symptom:**
```
[INFO] Chunk abc123: generated=2, verified=0, rejected=2
```

**Solutions:**

**Step 1: Check Rejection Reasons**
```bash
# View rejected items
cat workspace/rejected/my_project/rejected_items_*.jsonl | jq '.verification_report.errors'
```

**Step 2: Common Rejection Reasons**

| Error | Cause | Solution |
|-------|-------|----------|
| Missing thought tokens | Model didn't use special tokens | Update generation prompt |
| Missing boxed answer | No `\boxed{}` in solution | Add requirement to prompt |
| Improper nesting | Tokens in wrong order | Add examples to prompt |
| Verifier rejected | Content quality issues | Adjust verification prompt |

**Step 3: Disable Strict Checks (Temporary)**
```yaml
# config/app.config.yaml
verification:
  enabled: false  # Disable LLM verification
  local_checks:
    - json_schema
    - messages_shape
    # Remove strict checks temporarily
```

---

#### 4. Ollama Connection Issues

**Symptom:**
```
[ERROR] Failed to connect to http://localhost:11434/v1
```

**Solutions:**

**Step 1: Verify Ollama is Running**
```bash
ollama ps
```

**Step 2: Check Models are Installed**
```bash
ollama list
```

**Step 3: Test Connection**
```bash
python test_ollama_connection.py
```

**Step 4: Restart Ollama**
```bash
# Windows
Restart-Service Ollama

# Linux/Mac
systemctl restart ollama
```

---

#### 5. Out of Memory Errors

**Symptom:**
```
[ERROR] CUDA out of memory
```

**Solutions:**

**Option A: Reduce Batch Size**
```yaml
# config/app.config.yaml
runtime:
  parallel_chunks: 1  # Process one at a time
```

**Option B: Use Smaller Model**
```yaml
generation:
  model_name: "qwen3:8b"  # Instead of gpt-oss:20b
```

**Option C: Reduce Context Length**
```yaml
chunking:
  max_tokens_per_chunk: 512  # Instead of 1024
```

---

### Debug Logging

Enable verbose logging for detailed diagnostics:

```bash
python -m src.script2_generate_verify --verbose
```

Log files are saved to `workspace/logs/`:
- `script1_*.log` - Chunking logs
- `script2_*.log` - Generation/verification logs
- `script3_*.log` - Packing logs
- `failed_json/*.txt` - JSON parsing debug files

---

## 🎓 Advanced Topics

### Using Different LLM Providers

#### OpenAI

```bash
# .env
API_BASE=https://api.openai.com/v1
API_KEY=sk-your-api-key-here
API_TIMEOUT=60
```

```yaml
# config/app.config.yaml
generation:
  model_name: "gpt-4-turbo-preview"
verification:
  model_name: "gpt-3.5-turbo"
runtime:
  parallel_chunks: 8
  timeout_seconds: 60
```

#### Anthropic (via OpenAI-compatible proxy)

```bash
# .env
API_BASE=https://api.anthropic.com/v1
API_KEY=sk-ant-your-api-key-here
API_TIMEOUT=60
```

```yaml
# config/app.config.yaml
generation:
  model_name: "claude-3-opus-20240229"
verification:
  model_name: "claude-3-haiku-20240307"
```

#### Azure OpenAI

```bash
# .env
API_BASE=https://your-resource.openai.azure.com/openai/deployments/your-deployment
API_KEY=your-azure-api-key
API_TIMEOUT=60
```

---

### Customizing Verification Checks

Add custom validation logic in `src/common/validation.py`:

```python
def validate_custom_check(item: dict) -> tuple[bool, str]:
    """Custom validation check."""
    solution = item['messages'][1]['content']

    # Example: Require citations
    if '[' not in solution or ']' not in solution:
        return False, "Missing citations"

    return True, ""

# Register the check
VALIDATION_CHECKS['custom_citations'] = validate_custom_check
```

Then enable in config:

```yaml
verification:
  local_checks:
    - json_schema
    - messages_shape
    - special_tokens
    - custom_citations  # Your custom check
```

---

### Adjusting Chunk Parameters

Fine-tune chunking for your content:

```yaml
chunking:
  max_tokens_per_chunk: 2048  # Larger chunks = more context
  overlap_tokens: 256          # More overlap = better continuity

  semantic_breaks:
    heading_1: 2000    # Stronger preference for breaking at H1
    heading_2: 1000    # Medium preference for H2
    heading_3: 500     # Weak preference for H3
    code_block: 200    # Break before code blocks
    list_item: 100     # Break at list items
    paragraph: 50      # Break at paragraphs
```

**Guidelines:**
- **Technical docs**: Larger chunks (1024-2048 tokens) for more context
- **Q&A content**: Smaller chunks (512-1024 tokens) for focused questions
- **Code-heavy**: Higher `code_block` weight to keep code together
- **Narrative**: Higher `paragraph` weight for natural breaks

---

### Performance Tuning

#### For Local LLMs (Ollama)

```yaml
runtime:
  parallel_chunks: 1              # Sequential processing
  timeout_seconds: 600            # 10 minutes
  max_requests_per_minute: 60     # Conservative rate limit

generation:
  max_tokens: 2048                # Shorter responses = faster
  temperature: 0.7                # Lower = more deterministic
```

#### For Cloud APIs (OpenAI, Anthropic)

```yaml
runtime:
  parallel_chunks: 8              # High parallelism
  timeout_seconds: 60             # 1 minute
  max_requests_per_minute: 500    # API tier dependent
  max_tokens_per_minute: 200000   # API tier dependent

generation:
  max_tokens: 4096                # Longer responses OK
  temperature: 0.8                # Higher creativity
```

---

### Batch Processing Multiple Projects

Process all projects in the input directory:

```bash
# Chunk all projects
python -m src.script1_chunk_md \
  --input-root ./input \
  --workspace ./workspace \
  --config ./config/app.config.yaml

# Generate for all projects
python -m src.script2_generate_verify \
  --workspace ./workspace \
  --config ./config/app.config.yaml \
  --parallel 1

# Pack all projects together
python -m src.script3_pack_json \
  --workspace ./workspace \
  --output ./output \
  --config ./config/app.config.yaml
```

---

## 🤝 Contributing

Contributions are welcome! Please:

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

### Development Setup

```bash
# Install with dev dependencies
pip install -e ".[dev]"

# Run tests
pytest

# Format code
black src/

# Lint code
ruff check src/

# Type check
mypy src/
```

---

## 📄 License

This project is licensed under the MIT License - see the LICENSE file for details.

---

## 🙏 Acknowledgments

- Built with [Ollama](https://ollama.ai/) for local LLM inference
- Uses [tiktoken](https://github.com/openai/tiktoken) for tokenization
- Inspired by the need for high-quality synthetic training data

---

## 📞 Support

For questions, issues, or feature requests:

- **GitHub Issues**: Report bugs or request features
- **GitHub Discussions**: Ask questions or share ideas
- **Documentation**: Check the `docs/` folder for detailed guides

---

## 📚 Additional Resources

- **Setup Guides**:
  - `UBUNTU_SETUP.md` - Complete Ubuntu/Linux setup with virtual environment
  - `requirements.txt` - Python dependencies list
  - `quickstart.sh` - Automated setup script (Linux/Mac)
  - `quickstart.ps1` - Automated setup script (Windows)
- **Sample Data**: See `input/sample_project/` for example markdown files
- **Test Scripts**:
  - `test_ollama_connection.py` - Test Ollama setup
  - `test_json_parsing.py` - Test JSON parsing utilities
  - `verify_chunks.py` - Verify chunked data
- **Configuration Examples**: See `config/` for all configuration files
- **Schemas**: See `schemas/` for JSON schema definitions

---

## 🔄 Version History

### v0.1.0 (2025-11-07)

**Initial Release:**
- ✅ Three-stage pipeline (chunking, generation/verification, packing)
- ✅ Ollama support for local LLM inference
- ✅ Robust JSON parsing with automatic error recovery
- ✅ 12 comprehensive validation checks
- ✅ Granular timeout configuration
- ✅ Parallel processing support
- ✅ Resume functionality
- ✅ Comprehensive logging and debugging

**Known Issues:**
- Large models (>20B parameters) may require significant timeout increases
- Verification can be slow with local LLMs
- Memory usage scales with parallelism

**Planned Features:**
- [ ] Support for more tokenizers (Llama, GPT-2, etc.)
- [ ] Web UI for monitoring pipeline progress
- [ ] Automatic prompt optimization
- [ ] Multi-turn conversation generation
- [ ] Integration with HuggingFace datasets
- [ ] Docker containerization

---

**Happy Dataset Generation! 🚀**
