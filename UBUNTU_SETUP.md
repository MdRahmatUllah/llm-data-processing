# Ubuntu Setup Guide

Complete guide for setting up the Synthetic SFT Dataset Generation Pipeline on Ubuntu.

---

## 📋 Prerequisites

### System Requirements

- **OS**: Ubuntu 20.04 LTS or later (also works on Debian-based distributions)
- **Python**: 3.10 or later
- **RAM**: 8GB minimum (16GB+ recommended for local LLMs)
- **Disk Space**: 10GB minimum (more if using large Ollama models)

---

## 🔧 Step 1: Install Python 3.10+

### Check Current Python Version

```bash
python3 --version
```

### If Python 3.10+ is Not Installed

#### Ubuntu 22.04 and later (Python 3.10+ included):

```bash
sudo apt update
sudo apt install python3 python3-pip python3-venv
```

#### Ubuntu 20.04 (requires PPA):

```bash
sudo apt update
sudo apt install software-properties-common
sudo add-apt-repository ppa:deadsnakes/ppa
sudo apt update
sudo apt install python3.10 python3.10-venv python3.10-dev
sudo apt install python3-pip
```

### Verify Installation

```bash
python3.10 --version
# Should output: Python 3.10.x or later
```

---

## 📦 Step 2: Create Virtual Environment

### Navigate to Project Directory

```bash
cd /path/to/data-processing
# Or if you're already in the project directory:
pwd  # Should show: /path/to/data-processing
```

### Create Virtual Environment

**Option A: Using default Python 3**
```bash
python3 -m venv venv
```

**Option B: Using specific Python version (e.g., 3.10)**
```bash
python3.10 -m venv venv
```

**Option C: Using custom name**
```bash
python3 -m venv .venv  # Hidden directory
```

This creates a `venv/` directory containing the isolated Python environment.

---

## ✅ Step 3: Activate Virtual Environment

### Activate the Environment

```bash
source venv/bin/activate
```

**You should see the prompt change to:**
```bash
(venv) user@hostname:~/data-processing$
```

### Verify Activation

```bash
which python
# Should output: /path/to/data-processing/venv/bin/python

python --version
# Should output: Python 3.10.x or later
```

---

## 📥 Step 4: Install Requirements

### Upgrade pip (Recommended)

```bash
pip install --upgrade pip
```

### Install All Dependencies

```bash
pip install -r requirements.txt
```

**Expected output:**
```
Collecting pyyaml>=6.0
  Downloading PyYAML-6.0.1-cp310-cp310-manylinux_2_17_x86_64.manylinux2014_x86_64.whl
Collecting jsonschema>=4.17.0
  ...
Successfully installed click-8.1.7 httpx-0.25.2 jinja2-3.1.2 ...
```

### Verify Installation

```bash
pip list
```

**Should show all installed packages:**
```
Package         Version
--------------- -------
click           8.1.7
httpx           0.25.2
jinja2          3.1.2
jsonschema      4.20.0
openai          1.6.1
pyyaml          6.0.1
...
```

### Alternative: Install in Editable Mode (Development)

If you want to modify the source code:

```bash
pip install -e .
```

This installs the package in editable mode, allowing you to make changes without reinstalling.

---

## 🎯 Step 5: Install Ollama (Optional - for Local LLMs)

### Download and Install Ollama

```bash
curl -fsSL https://ollama.com/install.sh | sh
```

### Start Ollama Service

```bash
# Start Ollama in the background
ollama serve &

# Or use systemd (if installed as service)
sudo systemctl start ollama
sudo systemctl enable ollama  # Auto-start on boot
```

### Pull Required Models

```bash
# Generation model (20B parameters - requires ~12GB RAM)
ollama pull gpt-oss:20b

# Verification model (8B parameters - requires ~5GB RAM)
ollama pull qwen3:8b
```

### Verify Ollama Installation

```bash
ollama list
```

**Expected output:**
```
NAME            ID              SIZE    MODIFIED
gpt-oss:20b     abc123def456    11 GB   2 minutes ago
qwen3:8b        def789ghi012    4.7 GB  1 minute ago
```

### Test Ollama API

```bash
curl http://localhost:11434/v1/models
```

---

## ⚙️ Step 6: Configure Environment

### Create .env File

```bash
cat > .env << 'EOF'
# API Configuration for Ollama
API_BASE=http://localhost:11434/v1
API_KEY=ollama
API_TIMEOUT=1200
EOF
```

### Verify Configuration

```bash
cat .env
```

---

## 🚀 Step 7: Run the Pipeline

### Quick Test with Sample Data

```bash
# Make quick start script executable
chmod +x quickstart.sh

# Run the complete pipeline
./quickstart.sh
```

### Manual Execution (Step by Step)

#### Step 1: Chunk Markdown Files

```bash
python -m src.script1_chunk_md \
  --input-root ./input \
  --project sample_project \
  --workspace ./workspace \
  --config ./config/app.config.yaml \
  --verbose
```

#### Step 2: Generate and Verify Q&A Pairs

```bash
python -m src.script2_generate_verify \
  --workspace ./workspace \
  --config ./config/app.config.yaml \
  --parallel 1 \
  --verbose
```

#### Step 3: Pack into Final Datasets

```bash
python -m src.script3_pack_json \
  --workspace ./workspace \
  --output ./output \
  --config ./config/app.config.yaml \
  --seed 42 \
  --verbose
```

---

## 🔄 Daily Workflow

### Activate Environment (Every Time)

```bash
cd /path/to/data-processing
source venv/bin/activate
```

### Deactivate Environment (When Done)

```bash
deactivate
```

### Update Dependencies

```bash
source venv/bin/activate
pip install --upgrade -r requirements.txt
```

---

## 🛠️ Troubleshooting

### Issue 1: "python3: command not found"

**Solution:**
```bash
sudo apt update
sudo apt install python3
```

### Issue 2: "venv: command not found"

**Solution:**
```bash
sudo apt install python3-venv
```

### Issue 3: "pip: command not found"

**Solution:**
```bash
sudo apt install python3-pip
```

### Issue 4: Permission Denied

**Solution:**
```bash
# Don't use sudo with pip in venv
# Instead, ensure venv is activated:
source venv/bin/activate
pip install -r requirements.txt
```

### Issue 5: "No module named 'distutils'"

**Solution (Ubuntu 20.04):**
```bash
sudo apt install python3.10-distutils
```

### Issue 6: Ollama Connection Failed

**Solution:**
```bash
# Check if Ollama is running
ps aux | grep ollama

# If not running, start it:
ollama serve &

# Or restart the service:
sudo systemctl restart ollama
```

### Issue 7: Out of Memory (OOM) with Large Models

**Solution:**
```bash
# Use smaller models
ollama pull qwen3:8b  # Instead of gpt-oss:20b

# Update config/app.config.yaml:
# generation:
#   model_name: "qwen3:8b"
```

---

## 📝 Additional Setup (Optional)

### Install Development Tools

```bash
source venv/bin/activate
pip install pytest pytest-asyncio black ruff mypy
```

### Run Tests

```bash
pytest
```

### Format Code

```bash
black src/
```

### Lint Code

```bash
ruff check src/
```

---

## 🔐 Security Best Practices

### 1. Never Commit .env File

```bash
# Already in .gitignore, but verify:
cat .gitignore | grep .env
```

### 2. Use Virtual Environment

Always activate venv before running scripts to avoid polluting system Python.

### 3. Keep Dependencies Updated

```bash
pip list --outdated
pip install --upgrade <package-name>
```

---

## 📚 Quick Reference

### Common Commands

```bash
# Activate venv
source venv/bin/activate

# Deactivate venv
deactivate

# Install requirements
pip install -r requirements.txt

# Update pip
pip install --upgrade pip

# List installed packages
pip list

# Check Python version
python --version

# Run quick start
./quickstart.sh

# Check Ollama status
ollama ps

# View logs
tail -f workspace/logs/script2_*.log
```

---

## 🎓 Next Steps

1. ✅ Virtual environment created and activated
2. ✅ Dependencies installed
3. ✅ Ollama configured (if using local LLMs)
4. ✅ Environment variables set

**Now you can:**
- Run the quick start script: `./quickstart.sh`
- Process your own markdown files
- Customize configuration in `config/app.config.yaml`
- Review the main README.md for detailed usage

---

## 📞 Support

For more information:
- **Main Documentation**: See `README.md`
- **Troubleshooting**: See README.md troubleshooting section
- **Configuration**: See `config/app.config.yaml`

---

**Setup Complete! 🚀**

Your Ubuntu environment is now ready to generate synthetic SFT datasets.

