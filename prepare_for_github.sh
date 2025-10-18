#!/bin/bash
# Prepare repository for GitHub push

echo "🧹 Preparing repository for GitHub..."
echo ""

# 1. Clean build artifacts
echo "1️⃣ Cleaning build artifacts..."
find . -type f -name "*.pyc" -delete 2>/dev/null
find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
find . -type d -name ".pytest_cache" -exec rm -rf {} + 2>/dev/null || true
rm -f dashboard/tsconfig.tsbuildinfo 2>/dev/null
echo "   ✓ Python cache cleaned"

# 2. Clean logs and databases
echo "2️⃣ Cleaning runtime files..."
rm -f logs/*.log logs/*.jsonl 2>/dev/null || true
rm -f data/*.db data/*.sqlite 2>/dev/null || true
echo "   ✓ Logs and databases cleaned (will regenerate)"

# 3. Verify .gitignore
echo "3️⃣ Checking .gitignore..."
if [ -f .gitignore ]; then
    echo "   ✓ .gitignore exists"
else
    echo "   ❌ .gitignore missing!"
    exit 1
fi

# 4. Check for sensitive files
echo "4️⃣ Checking for sensitive files..."
if [ -f polygon_api.txt ] || [ -f pplx_api.txt ] || [ -f alpaca.txt ]; then
    echo "   ⚠️  WARNING: API key files found!"
    echo "   These will be ignored by Git (check .gitignore)"
    echo "   Make sure polygon_api.txt.example exists instead"
fi

if [ -f polygon_api.txt.example ]; then
    echo "   ✓ polygon_api.txt.example exists"
else
    echo "   ❌ polygon_api.txt.example missing!"
fi

# 5. Initialize Git if needed
echo "5️⃣ Checking Git status..."
if [ ! -d .git ]; then
    echo "   Initializing Git repository..."
    git init
    echo "   ✓ Git initialized"
else
    echo "   ✓ Git already initialized"
fi

# 6. Show what will be committed
echo ""
echo "📦 Files ready to commit:"
git add -A --dry-run 2>/dev/null | head -20 || echo "   (Run 'git add -A' to stage files)"

echo ""
echo "✅ Repository is clean and ready!"
echo ""
echo "📝 Next steps:"
echo "   1. Review files: git status"
echo "   2. Stage files: git add -A"
echo "   3. Commit: git commit -m 'Initial commit: TEPM Analytics Dashboard'"
echo "   4. Add remote: git remote add origin <your-github-url>"
echo "   5. Push: git push -u origin main"
echo ""

