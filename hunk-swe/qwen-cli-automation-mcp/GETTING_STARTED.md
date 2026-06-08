# Getting Started with SWE-bench Qwen Automation

This guide provides complete step-by-step instructions for setting up and running the Qwen Code CLI automation on SWE-bench Verified multi-hunk bugs.

## Table of Contents

- [Overview](#overview)
- [Prerequisites](#prerequisites)
- [Step-by-Step Setup](#step-by-step-setup)
- [Running the Automation](#running-the-automation)
- [Understanding the Output](#understanding-the-output)
- [Troubleshooting](#troubleshooting)
- [Advanced Usage](#advanced-usage)

## Overview

The Qwen automation runs the Qwen Code CLI agent inside Docker containers to repair Python bugs from SWE-bench Verified. Each bug runs in its own isolated container with the correct Python version, conda environment, and dependencies pre-installed.

**Key features:**
- Docker-isolated per-instance evaluation
- Pinned CLI version: `@qwen-code/qwen-code@0.0.11`
- Official SWE-bench harness grading (bit-identical to leaderboard)
- Structured trajectory capture (JSONL format)
- Automatic image building and caching

## Prerequisites

Before you begin, ensure you have:

### 1. Docker Desktop

Docker must be installed and running on your system.

**Installation:**
- macOS: Download from [Docker Desktop for Mac](https://www.docker.com/products/docker-desktop/)
- Linux: Follow [Docker Engine installation](https://docs.docker.com/engine/install/)
- Windows: Download from [Docker Desktop for Windows](https://www.docker.com/products/docker-desktop/)

**Resource allocation:**
- Allocate **~30 GB free space** in Docker Desktop disk image
- Settings → Resources → Disk image size
- Base images + per-instance overlays + grader caches add up quickly

**Verify Docker is running:**
```bash
docker ps
```

If you see a table of running containers (or an empty table), Docker is ready.

### 2. Conda

You need Conda (Anaconda or Miniconda) installed to create the Python environment.

**Installation:**
- Miniconda (recommended): https://docs.conda.io/en/latest/miniconda.html
- Anaconda: https://www.anaconda.com/download

### 3. API Key

You need an API key for accessing the Qwen model:

**Option A: OpenRouter (Recommended)**
- Sign up at: https://openrouter.ai/
- Create API key in your dashboard
- Supports `qwen/qwen3-coder-flash` model
- More cost-effective for Qwen models

**Option B: OpenAI API**
- Sign up at: https://platform.openai.com/
- Create API key in your account settings
- Can be used with custom OpenAI-compatible endpoints

## Step-by-Step Setup

### Step 1: Start Docker Desktop

Launch Docker Desktop application and wait until it's fully running.

**Verify:**
```bash
docker ps
```

Expected output: A table showing running containers (may be empty).

### Step 2: Navigate to Repository

```bash
cd /path/to/agentic-multihunk-repair/hunk-swe
```

Replace `/path/to/` with your actual repository path.

### Step 3: Create Conda Environment

Create the `swe-bench-eval` conda environment:

```bash
# Create environment from YAML file
conda env create -f environment.yml

# Activate the environment
conda activate swe-bench-eval
```

This installs:
- Python 3.10
- SWE-bench harness (>=4.1.0)

**Verify:**
```bash
conda info --envs | grep swe-bench-eval
python --version  # Should show Python 3.10.x
```

### Step 4: Install NLTK and punkt_tab Tokenizer

The hunk divergence metrics require NLTK with the `punkt_tab` tokenizer:

```bash
# Ensure you're in the swe-bench-eval environment
conda activate swe-bench-eval

# Install NLTK
pip install nltk

# Download punkt_tab tokenizer
python -c "import nltk; nltk.download('punkt_tab')"
```

**Verify:**
```bash
python -c "import nltk; print(nltk.data.find('tokenizers/punkt_tab'))"
```

Should print the path to the tokenizer data.

### Step 5: Navigate to Qwen Automation Directory

```bash
cd qwen-cli-automation
```

Your working directory should now be: `.../hunk-swe/qwen-cli-automation/`

### Step 6: Create .env File with API Key

Create a `.env` file with your API key:

**Option A: Using OpenRouter (Recommended)**
```bash
echo "OPENROUTER_API_KEY=your_actual_api_key_here" > .env
```

**Option B: Using OpenAI API**
```bash
echo "OPENAI_API_KEY=your_actual_api_key_here" > .env
```

**Security note:** Never commit `.env` files to version control. The `.gitignore` should already exclude it.

**Verify:**
```bash
cat .env
```

Should show your API key (ensure it's correct).

### Step 7: Verify Complete Setup

Run these checks to ensure everything is ready:

```bash
# 1. Docker is running
docker ps

# 2. Conda environment is active
echo $CONDA_DEFAULT_ENV  # Should show: swe-bench-eval

# 3. Python version is correct
python --version  # Should show: Python 3.10.x

# 4. SWE-bench harness is installed
python -c "import swebench; print(swebench.__version__)"

# 5. .env file exists
ls -la .env

# 6. Working directory is correct
pwd  # Should end with: .../hunk-swe/qwen-cli-automation
```

All checks should pass before proceeding.

## Running the Automation

### Quick Start: Run a Single Bug

```bash
python3 automated_qwen_code.py --only astropy__astropy-13033
```

This will:
1. Build the overlay Docker image (first time: ~2-5 minutes)
2. Start a container with the bug's repository
3. Run Qwen agent inside the container (30-minute timeout)
4. Extract the patch and grade it
5. Save results to `workspace_docker/astropy__astropy-13033/logs/`

### Available Instance IDs (32 Multi-hunk Bugs)

**Astropy (8 bugs):**
- `astropy__astropy-13033`
- `astropy__astropy-13579`
- `astropy__astropy-14365`
- `astropy__astropy-14369`
- `astropy__astropy-14598`
- `astropy__astropy-7606`
- `astropy__astropy-8707`
- `astropy__astropy-8872`

**Django (16 bugs):**
- `django__django-10554`, `django__django-11138`, `django__django-11400`
- `django__django-11532`, `django__django-11728`, `django__django-11740`
- `django__django-12406`, `django__django-13343`, `django__django-13346`
- `django__django-13449`, `django__django-15128`, `django__django-15503`
- `django__django-15563`, `django__django-15572`, `django__django-15732`
- `django__django-16631`

**Scikit-learn (7 bugs):**
- `scikit-learn__scikit-learn-10297`
- `scikit-learn__scikit-learn-14087`
- `scikit-learn__scikit-learn-25232`
- `scikit-learn__scikit-learn-25747`
- `scikit-learn__scikit-learn-25931`
- `scikit-learn__scikit-learn-26194`
- `scikit-learn__scikit-learn-26323`

**SymPy (1 bug):**
- `sympy__sympy-13877`

### Common Usage Patterns

**Run multiple specific bugs:**
```bash
python3 automated_qwen_code.py --only astropy__astropy-13033 django__django-11138
```

**Run with custom timeout (20 minutes):**
```bash
python3 automated_qwen_code.py --only astropy__astropy-13033 --duration-min 20
```

**Resume from a specific bug:**
```bash
python3 automated_qwen_code.py --start-from django__django-15128
```

**Keep container running for debugging:**
```bash
python3 automated_qwen_code.py --only astropy__astropy-13033 --keep-container
```

Then inspect the container:
```bash
docker ps  # Find the container name
docker exec -it <container_name> bash -l
```

**Run all 32 bugs:**
```bash
python3 automated_qwen_code.py
```

**Skip image building (requires pre-built images):**
```bash
python3 automated_qwen_code.py --only astropy__astropy-13033 --no-build
```

### Command-Line Options

```
--model                 Model name (default: qwen/qwen3-coder-flash)
--openai-base-url       API endpoint (default: https://openrouter.ai/api/v1)
--workspace             Host directory for logs/patches (default: ./workspace_docker)
--base-prompt           Prompt template file (default: ../swe_bench_utils/prompt.md)
--env-file              API key file (default: ./.env)
--image-base            Docker registry (default: swebench/sweb.eval.x86_64)
--image-tag             Base image tag (default: v2)
--overlay-prefix        Overlay image prefix (default: qwen-eval)
--node-major            Node.js major version (default: 20)
--qwen-version          Qwen CLI npm version (default: 0.0.11)
--no-build              Skip overlay image build
--keep-container        Keep container running after execution
--duration-min          Per-bug timeout in minutes (default: 30)
--results-base          Results directory (default: ./results)
--results-tag           Results CSV tag (default: qwen)
--only                  Run only specific bugs (space-separated)
--start-from            Resume from specific bug (inclusive)
--processed-json        Progress tracking file (default: ./config/processed_qwen.json)
--manifest              Image manifest file (default: ./image_manifest.json)
--run-id-suffix         SWE-bench run ID suffix (default: run1)
```

## Understanding the Output

### Directory Structure

After running, you'll see this structure:

```
qwen-cli-automation/
├── workspace_docker/
│   └── <instance_id>/
│       ├── agent_logs/                    # Bind-mounted logs from container
│       │   ├── qwen-trajectory-<ts>.json  # Agent trajectory (JSONL)
│       │   └── qwen-telemetry-<ts>.json   # Telemetry data
│       └── logs/
│           ├── run-<ts>.log               # Console output
│           ├── qwen-trajectory-<ts>.json  # Mirrored trajectory
│           ├── qwen-telemetry-<ts>.json   # Mirrored telemetry
│           ├── patch-<ts>.diff            # Final patch
│           ├── swebench_report.json       # Official harness verdict
│           ├── swebench_eval.sh           # Grader script
│           ├── swebench_test_output.txt   # Test output
│           └── swebench_grader/           # Grader container artifacts
├── results/
│   └── test_results_model_qwen.csv        # Aggregated results
├── config/
│   └── processed_qwen.json                # Progress tracking
└── image_manifest.json                    # Docker image reproducibility manifest
```

### Results CSV

`results/test_results_model_qwen.csv` contains one row per bug:

| Column | Description |
|--------|-------------|
| `instance_id` | Bug identifier |
| `resolved` | Yes/No - All fail-to-pass tests pass, no regressions |
| `fail_to_pass_resolved` | Yes/No - Bug-exposing tests now pass |
| `no_regressions` | Yes/No - No pass-to-fail tests |
| `failed_tests` | Semicolon-separated list of failed tests |
| `duration_s` | Total execution time in seconds |
| `error` | Error message if any |

### Grader Report

`workspace_docker/<instance_id>/logs/swebench_report.json` is produced by the official SWE-bench harness:

```json
{
  "<instance_id>": {
    "resolved": true,
    "tests_status": {
      "FAIL_TO_PASS": {
        "success": ["test_foo", "test_bar"],
        "failure": []
      },
      "PASS_TO_PASS": {
        "success": [...],
        "failure": []
      }
    }
  }
}
```

### Progress Tracking

`config/processed_qwen.json` tracks completed bugs:

```json
[
  "astropy__astropy-13033",
  "django__django-11138"
]
```

This allows resuming interrupted runs with `--start-from` or automatically skipping completed bugs.

### Image Manifest

`image_manifest.json` records Docker image details for reproducibility:

```json
[
  {
    "instance_id": "astropy__astropy-13033",
    "base_image": "swebench/sweb.eval.x86_64.astropy__astropy-13033:v2",
    "base_digest": "sha256:...",
    "overlay_image": "qwen-eval/astropy__astropy-13033",
    "overlay_digest": "sha256:...",
    "node_major": 20,
    "cli_package": "@qwen-code/qwen-code",
    "cli_version": "0.0.11"
  }
]
```

## Troubleshooting

### Docker Issues

**Problem:** `docker ps` fails or shows connection error

**Solution:**
```bash
# Ensure Docker Desktop is running
# On macOS: Check if Docker Desktop app is running in menu bar
# On Linux: sudo systemctl start docker

# Verify Docker daemon is accessible
docker info
```

**Problem:** Out of disk space in Docker

**Solution:**
```bash
# Check Docker disk usage
docker system df

# Clean up unused images and containers
docker system prune -a

# Increase disk image size in Docker Desktop settings
# Settings → Resources → Disk image size → Increase to ~50-60 GB
```

### Conda Environment Issues

**Problem:** `conda: command not found`

**Solution:**
```bash
# Initialize conda for your shell
conda init bash  # or zsh, fish, etc.

# Restart your shell
exec $SHELL
```

**Problem:** Wrong Python version

**Solution:**
```bash
# Ensure you're in the swe-bench-eval environment
conda activate swe-bench-eval

# Verify
python --version  # Should show Python 3.10.x
```

### API Key Issues

**Problem:** `OPENROUTER_API_KEY nor OPENAI_API_KEY found`

**Solution:**
```bash
# Verify .env file exists and contains the key
cat .env

# Check format (no spaces around =)
# Correct: OPENROUTER_API_KEY=sk-...
# Wrong:   OPENROUTER_API_KEY = sk-...

# Ensure you're in the qwen-cli-automation directory
pwd
```

**Problem:** API authentication failures

**Solution:**
```bash
# Test your API key
curl -H "Authorization: Bearer $OPENROUTER_API_KEY" \
     https://openrouter.ai/api/v1/models

# If using OpenAI, test with:
curl -H "Authorization: Bearer $OPENAI_API_KEY" \
     https://api.openai.com/v1/models
```

### Container Issues

**Problem:** Container fails to start

**Solution:**
```bash
# Check Docker logs
docker logs <container_name>

# Try rebuilding the overlay image
python3 automated_qwen_code.py --only <instance_id>
# (don't use --no-build)

# Verify base image can be pulled
docker pull swebench/sweb.eval.x86_64.<repo>__<repo>-<issue>:v2
```

**Problem:** Container runs but agent fails

**Solution:**
```bash
# Keep container running for debugging
python3 automated_qwen_code.py --only <instance_id> --keep-container

# Inspect the container
docker ps  # Get container name
docker exec -it <container_name> bash -l

# Inside container, check:
which qwen  # Should be in /usr/local/bin or similar
qwen --version  # Should show 0.0.11
cd /testbed && ls  # Check repository is present
cat AGENT.md  # Check prompt was injected
```

### NLTK Issues

**Problem:** `punkt_tab` tokenizer not found

**Solution:**
```bash
# Download punkt_tab explicitly
python -c "import nltk; nltk.download('punkt_tab')"

# Verify
python -c "import nltk; print(nltk.data.find('tokenizers/punkt_tab'))"

# If still failing, try:
python -c "import nltk; nltk.download('punkt')"
```

### SWE-bench Harness Issues

**Problem:** Import error: `No module named 'swebench'`

**Solution:**
```bash
# Ensure you're in the correct conda environment
conda activate swe-bench-eval

# Reinstall swebench
pip install --upgrade swebench

# Verify
python -c "import swebench; print(swebench.__version__)"
```

**Problem:** Grading fails with weird errors

**Solution:**
```bash
# Check logs in workspace_docker/<instance_id>/logs/swebench_test_output.txt
# Common issues:
# - Stale IERS data (Astropy bugs) - this is expected and handled
# - NumPy/SciPy ABI warnings - usually harmless
# - Network disabled in grader container - expected for reproducibility

# The harness handles these automatically; check if the error
# is in the agent's execution or the grader's baseline
```

### Build Issues

**Problem:** Overlay image build fails

**Solution:**
```bash
# Check Node.js installation in Dockerfile
# Manually build to see detailed errors:
docker build -f ../swe_bench_utils/Dockerfile.overlay \
  --build-arg BASE_IMAGE=swebench/sweb.eval.x86_64.<instance>:v2 \
  --build-arg NODE_MAJOR=20 \
  --build-arg CLI_PACKAGE=@qwen-code/qwen-code \
  --build-arg CLI_VERSION=0.0.11 \
  --build-arg CLI_BINARY=qwen \
  -t test-overlay .

# Check if npm registry is accessible
docker run --rm node:20 npm info @qwen-code/qwen-code
```

## Advanced Usage

### Using a Different Model

```bash
# Use a different Qwen model variant
python3 automated_qwen_code.py \
  --only astropy__astropy-13033 \
  --model qwen/qwen3-coder-instruct

# Use with local vLLM server
python3 automated_qwen_code.py \
  --only astropy__astropy-13033 \
  --openai-base-url http://localhost:8000/v1 \
  --model qwen3-coder
```

### Custom Prompt

```bash
# Create your own prompt template
cp ../swe_bench_utils/prompt.md my_prompt.md
# Edit my_prompt.md...

# Run with custom prompt
python3 automated_qwen_code.py \
  --only astropy__astropy-13033 \
  --base-prompt my_prompt.md
```

### Parallel Execution

```bash
# Run multiple bugs in parallel (advanced users)
# In terminal 1:
python3 automated_qwen_code.py --only astropy__astropy-13033

# In terminal 2:
python3 automated_qwen_code.py --only django__django-11138

# Note: Ensure you have enough Docker resources
```

### Inspecting Agent Behavior

```bash
# Extract command sequences from trajectory
python3 -c "
import json
trajectory = json.load(open('workspace_docker/astropy__astropy-13033/logs/qwen-trajectory-*.json'))
# Process trajectory...
"

# View telemetry data
cat workspace_docker/astropy__astropy-13033/logs/qwen-telemetry-*.json | jq .
```

### Reproducing Results

Using the `image_manifest.json`, you can reproduce exact results:

```bash
# Check manifest for specific bug
cat image_manifest.json | jq '.[] | select(.instance_id=="astropy__astropy-13033")'

# Pull and run the exact images
docker pull swebench/sweb.eval.x86_64.astropy__astropy-13033:v2@sha256:...
docker pull qwen-eval/astropy__astropy-13033@sha256:...
```

## Next Steps

After successful setup:

1. **Run the full evaluation:**
   ```bash
   python3 automated_qwen_code.py
   ```

2. **Analyze results:**
   - Check `results/test_results_model_qwen.csv` for overall statistics
   - Review individual patches in `workspace_docker/<id>/logs/patch-*.diff`
   - Examine agent trajectories for behavioral analysis

3. **Compute metrics:**
   - Hunk divergence: `../swe_hunk_divergence/hunk_divergence.py`
   - Proximity classification: `../swe_proximity_class/proximity_class.py`

4. **Compare with other agents:**
   - See `../gemini-cli-automation/` and `../codex-cli-automation/`

## Additional Resources

- **Main README:** `../README.md` (if exists)
- **Docker utils:** `../swe_bench_utils/README.md`
- **Qwen Code CLI docs:** https://github.com/QwenLM/qwen-code (check for 0.0.11 docs)
- **SWE-bench paper:** https://www.swebench.com/
- **OpenRouter docs:** https://openrouter.ai/docs

## Support

For issues specific to:
- **This automation:** Open an issue in the repository
- **Qwen Code CLI:** Check the official Qwen Code repository
- **SWE-bench harness:** See the SWE-bench GitHub repository
- **Docker:** Consult Docker documentation

## License

This automation framework is part of the "Agentic Multi-hunk Repair" research project. Refer to the repository's main LICENSE file for details.
