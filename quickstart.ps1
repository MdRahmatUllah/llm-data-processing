# Quick Start Script for Synthetic SFT Dataset Generation Pipeline (PowerShell)
# This script runs the complete pipeline on the sample project

$ErrorActionPreference = "Stop"

Write-Host "==========================================" -ForegroundColor Cyan
Write-Host "Synthetic SFT Dataset Generation Pipeline" -ForegroundColor Cyan
Write-Host "Quick Start Script" -ForegroundColor Cyan
Write-Host "==========================================" -ForegroundColor Cyan
Write-Host ""

# Check if Python is installed
try {
    $pythonVersion = python --version
    Write-Host "✓ Python found: $pythonVersion" -ForegroundColor Green
} catch {
    Write-Host "Error: Python is not installed" -ForegroundColor Red
    exit 1
}
Write-Host ""

# Step 1: Install dependencies
Write-Host "Step 1: Installing dependencies..." -ForegroundColor Blue
try {
    pip install -e .
    Write-Host "✓ Dependencies installed" -ForegroundColor Green
} catch {
    Write-Host "Warning: Installation failed. Trying manual install..." -ForegroundColor Yellow
    pip install pyyaml jsonschema jinja2 tiktoken sentencepiece openai httpx tenacity python-dotenv tqdm click
    Write-Host "✓ Dependencies installed" -ForegroundColor Green
}
Write-Host ""

# Check if .env exists
if (-not (Test-Path .env)) {
    Write-Host "Warning: .env file not found. Creating default .env for Ollama..." -ForegroundColor Yellow
    @"
# API Configuration for Ollama
API_BASE=http://localhost:11434/v1
API_KEY=ollama
API_TIMEOUT=1200
"@ | Out-File -FilePath .env -Encoding UTF8
    Write-Host "✓ Created .env file" -ForegroundColor Green
}
Write-Host ""

# Check if Ollama is running
Write-Host "Checking Ollama connection..." -ForegroundColor Blue
try {
    $ollamaCheck = ollama ps 2>&1
    Write-Host "✓ Ollama is running" -ForegroundColor Green
    Write-Host "Available models:" -ForegroundColor Cyan
    ollama list
} catch {
    Write-Host "Warning: Ollama is not running. Please start Ollama first." -ForegroundColor Yellow
    Write-Host "Run: ollama serve" -ForegroundColor Yellow
    exit 1
}
Write-Host ""

# Create necessary directories
Write-Host "Step 2: Creating directories..." -ForegroundColor Blue
New-Item -ItemType Directory -Path workspace/chunks -Force | Out-Null
New-Item -ItemType Directory -Path workspace/verified -Force | Out-Null
New-Item -ItemType Directory -Path workspace/rejected -Force | Out-Null
New-Item -ItemType Directory -Path workspace/logs -Force | Out-Null
New-Item -ItemType Directory -Path output -Force | Out-Null
Write-Host "✓ Directories created" -ForegroundColor Green
Write-Host ""

# Step 1: Chunking
Write-Host "Step 3: Chunking sample markdown file..." -ForegroundColor Blue
python -m src.script1_chunk_md `
  --input-root ./input `
  --project sample_project `
  --workspace ./workspace `
  --config ./config/app.config.yaml `
  --verbose

Write-Host "✓ Chunking complete" -ForegroundColor Green
Write-Host ""

# Show chunk statistics
$chunkFiles = Get-ChildItem -Path workspace/chunks/sample_project -Filter *.jsonl -Recurse
$chunkCount = ($chunkFiles | ForEach-Object { (Get-Content $_.FullName | Measure-Object -Line).Lines } | Measure-Object -Sum).Sum
Write-Host "Generated $chunkCount chunks" -ForegroundColor Cyan
Write-Host ""

# Step 2: Generation & Verification
Write-Host "Step 4: Generating and verifying Q&A pairs..." -ForegroundColor Blue
Write-Host "This may take 1-2 hours with Ollama (20B model)" -ForegroundColor Yellow
Write-Host "Press Ctrl+C to cancel, or wait for completion..." -ForegroundColor Yellow
Write-Host ""

python -m src.script2_generate_verify `
  --workspace ./workspace `
  --config ./config/app.config.yaml `
  --parallel 1 `
  --verbose

Write-Host "✓ Generation and verification complete" -ForegroundColor Green
Write-Host ""

# Show generation statistics
$verifiedCount = 0
$rejectedCount = 0

if (Test-Path workspace/verified/sample_project) {
    $verifiedFiles = Get-ChildItem -Path workspace/verified/sample_project -Filter *.jsonl -Recurse
    if ($verifiedFiles) {
        $verifiedCount = ($verifiedFiles | ForEach-Object { (Get-Content $_.FullName | Measure-Object -Line).Lines } | Measure-Object -Sum).Sum
    }
}

if (Test-Path workspace/rejected/sample_project) {
    $rejectedFiles = Get-ChildItem -Path workspace/rejected/sample_project -Filter *.jsonl -Recurse
    if ($rejectedFiles) {
        $rejectedCount = ($rejectedFiles | ForEach-Object { (Get-Content $_.FullName | Measure-Object -Line).Lines } | Measure-Object -Sum).Sum
    }
}

Write-Host "Verified items: $verifiedCount" -ForegroundColor Cyan
Write-Host "Rejected items: $rejectedCount" -ForegroundColor Cyan
Write-Host ""

# Step 3: Packing
Write-Host "Step 5: Packing into final datasets..." -ForegroundColor Blue
python -m src.script3_pack_json `
  --workspace ./workspace `
  --output ./output `
  --config ./config/app.config.yaml `
  --seed 42 `
  --verbose

Write-Host "✓ Packing complete" -ForegroundColor Green
Write-Host ""

# Show final statistics
Write-Host "==========================================" -ForegroundColor Cyan
Write-Host "Pipeline Complete!" -ForegroundColor Green
Write-Host "==========================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "Output files:" -ForegroundColor Cyan
Get-ChildItem -Path output | Format-Table Name, Length, LastWriteTime
Write-Host ""
Write-Host "Next steps:" -ForegroundColor Yellow
Write-Host "1. Review the generated datasets in output/" -ForegroundColor White
Write-Host "2. Check logs in workspace/logs/ for details" -ForegroundColor White
Write-Host "3. Use the datasets for fine-tuning your model" -ForegroundColor White
Write-Host ""
Write-Host "For more information, see README.md" -ForegroundColor Cyan

