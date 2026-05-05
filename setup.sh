#!/usr/bin/env bash
set -e

echo ""
echo " AI-OS v2 — Setup"
echo " ================"
echo ""

# Check Python
if ! command -v python3 &>/dev/null; then
    echo "[ERROR] Python 3 not found. Install Python 3.10+ from https://python.org"
    exit 1
fi
echo "[OK] Python found: $(python3 --version)"

# Check Node
if ! command -v node &>/dev/null; then
    echo "[ERROR] Node.js not found. Install Node.js 18+ from https://nodejs.org"
    exit 1
fi
echo "[OK] Node.js found: $(node --version)"

# Python dependencies
echo ""
echo "Installing Python dependencies..."
pip3 install -r requirements.txt
echo "[OK] Python dependencies installed"

# .env setup
if [ ! -f .env ]; then
    cp .env.example .env
    echo "[OK] Created .env from example"
    echo ""
    echo " !! Open .env and add your ANTHROPIC_API_KEY before starting."
    echo " !! Get your key at https://console.anthropic.com"
else
    echo "[OK] .env already exists"
fi

# Frontend dependencies
echo ""
echo "Installing frontend dependencies..."
cd frontend
npm install
npm run build
cd ..
echo "[OK] Frontend dependencies installed and built"

echo ""
echo " Setup complete!"
echo ""
echo " Next steps:"
echo "   1. Open .env and fill in your API keys"
echo "   2. Fill in knowledge_base/thesis/investment_thesis.md"
echo "   3. Run: ./start.sh"
echo ""
