#!/usr/bin/env bash
set -euo pipefail

ENV_NAME="labellix-studio"
ENV_FILE="environment.yml"

if ! command -v conda >/dev/null 2>&1; then
    echo "Error: conda not found in PATH. Install Miniconda or Anaconda first." >&2
    exit 1
fi

if [[ ! -f "$ENV_FILE" ]]; then
    echo "Error: $ENV_FILE not found. Run this script from the project root." >&2
    exit 1
fi

# Ensure conda shell functions are available in this script session.
source "$(conda info --base)/etc/profile.d/conda.sh"

if conda env list | awk '{print $1}' | grep -Fxq "$ENV_NAME"; then
    echo "Updating existing conda environment: $ENV_NAME"
    conda env update -f "$ENV_FILE" --prune
else
    echo "Creating conda environment: $ENV_NAME"
    conda env create -f "$ENV_FILE"
fi

echo
echo "Environment setup complete."
echo "Activate it with: conda activate $ENV_NAME"
echo "Run app with: python labellix_studio.py"
