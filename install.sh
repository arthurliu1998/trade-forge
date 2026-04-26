#!/bin/bash
set -euo pipefail

QUANTFORGE_HOME="$HOME/.quantforge"
REPO_DIR="$(cd "$(dirname "$0")" && pwd)"

echo "=== QuantForge Installer ==="

# 1. Create data directory structure
echo "[1/6] Creating data directories..."
mkdir -p "$QUANTFORGE_HOME"/{data,runs,backups,logs}

# 2. Set up Python virtual environment
echo "[2/6] Setting up Python environment..."
if [ ! -d "$QUANTFORGE_HOME/.venv" ]; then
    python3 -m venv "$QUANTFORGE_HOME/.venv"
fi
source "$QUANTFORGE_HOME/.venv/bin/activate"
pip install -q -r "$REPO_DIR/requirements.txt"

# 3. Copy config templates (don't overwrite existing)
echo "[3/6] Setting up configuration..."
if [ ! -f "$QUANTFORGE_HOME/.env" ]; then
    cp "$REPO_DIR/.env.example" "$QUANTFORGE_HOME/.env"
    echo "  Created .env — edit $QUANTFORGE_HOME/.env to add API keys"
else
    echo "  .env already exists — skipping"
fi

if [ ! -f "$QUANTFORGE_HOME/config.yaml" ]; then
    cp "$REPO_DIR/config.yaml.example" "$QUANTFORGE_HOME/config.yaml"
    echo "  Created config.yaml — edit to set your watchlist"
else
    echo "  config.yaml already exists — skipping"
fi

# 4. Set file permissions
echo "[4/6] Setting file permissions..."
chmod 700 "$QUANTFORGE_HOME"
chmod 600 "$QUANTFORGE_HOME/.env" 2>/dev/null || true
chmod 600 "$QUANTFORGE_HOME/config.yaml" 2>/dev/null || true
chmod 700 "$QUANTFORGE_HOME"/{runs,backups,logs}

# 5. Install trading experience system
echo "[5/7] Installing trading experience system..."
TRADING_NOTES="$HOME/.claude/notes/trading"
TRADING_SRC="$REPO_DIR/docs/trading-experience"
if [ -d "$TRADING_SRC" ]; then
    mkdir -p "$TRADING_NOTES/cases"
    # Copy reference files (always overwrite — these are templates/references)
    for f in playbook.md diagnostics.md patterns.md learning-log.md; do
        if [ ! -f "$TRADING_NOTES/$f" ] || [ "$1" = "--update" ]; then
            cp "$TRADING_SRC/$f" "$TRADING_NOTES/$f"
        fi
    done
    # Cases index — only if not exists (preserve user's recorded cases)
    [ ! -f "$TRADING_NOTES/cases.md" ] && cp "$TRADING_SRC/cases.md" "$TRADING_NOTES/cases.md"
    # Template and README — always update
    cp "$TRADING_SRC/cases/case-000-template.md" "$TRADING_NOTES/cases/"
    cp "$TRADING_SRC/cases/README.md" "$TRADING_NOTES/cases/"
    echo "  Trading experience files installed to $TRADING_NOTES"
else
    echo "  No trading experience docs found — skipping"
fi

# 6. Install git hooks (if in a git repo)
echo "[6/7] Installing git safety hooks..."
if [ -d "$REPO_DIR/.git" ]; then
    HOOK="$REPO_DIR/.git/hooks/pre-commit"
    cat > "$HOOK" << 'HOOKEOF'
#!/bin/bash
# Block sensitive files from being committed
for pattern in ".env" "portfolio.db" "config.yaml" "*.sqlite" "audit.log"; do
    if git diff --cached --name-only | grep -q "$pattern"; then
        echo "ERROR: Attempting to commit sensitive file matching '$pattern'"
        echo "Remove with: git reset HEAD <file>"
        exit 1
    fi
done
HOOKEOF
    chmod +x "$HOOK"
    echo "  Pre-commit hook installed"
else
    echo "  Not a git repo — skipping hooks"
fi

# 7. Check for git history leaks
echo "[7/7] Security checks..."
if [ -d "$REPO_DIR/.git" ]; then
    if git -C "$REPO_DIR" log --all --diff-filter=A --name-only 2>/dev/null | grep -q '\.env$'; then
        echo "  WARNING: .env was previously tracked in git history!"
        echo "  Run: git filter-repo --path .env --invert-paths"
    else
        echo "  No leaked secrets detected in git history"
    fi
else
    echo "  Not a git repo — skipping"
fi

echo ""
echo "=== QuantForge installed ==="
echo "Next steps:"
echo "  1. Edit $QUANTFORGE_HOME/.env to add API keys"
echo "  2. Edit $QUANTFORGE_HOME/config.yaml to set your watchlist"
echo "  3. Activate: source $QUANTFORGE_HOME/.venv/bin/activate"
echo "  4. Test: cd $REPO_DIR && python -m pytest tests/ -v"
