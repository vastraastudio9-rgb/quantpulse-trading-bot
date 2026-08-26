#!/bin/bash
# QuantPulse VPS Deployment Script
# Usage: bash deploy-vps.sh
# Run this on a fresh Ubuntu/Debian VPS

set -e

echo "================================================"
echo "  QuantPulse VPS Deployment"
echo "================================================"
echo ""

# Check OS
if [[ -f /etc/os-release ]]; then
  . /etc/os-release
  echo "OS: $NAME $VERSION"
else
  echo "Warning: Could not detect OS. Assuming Ubuntu/Debian."
fi

# === INSTALL SYSTEM DEPENDENCIES ===
echo ""
echo "[1/7] Installing system dependencies..."
sudo apt-get update -qq
sudo apt-get install -y -qq curl git python3 python3-pip python3-venv nodejs npm 2>/dev/null || {
  echo "Installing Node.js via NodeSource..."
  curl -fsSL https://deb.nodesource.com/setup_20.x | sudo -E bash -
  sudo apt-get install -y nodejs
}

# Install bun
if ! command -v bun &> /dev/null; then
  echo "Installing Bun..."
  curl -fsSL https://bun.sh/install | bash
  export BUN_INSTALL="$HOME/.bun"
  export PATH="$BUN_INSTALL/bin:$PATH"
  echo 'export BUN_INSTALL="$HOME/.bun"' >> ~/.bashrc
  echo 'export PATH="$BUN_INSTALL/bin:$PATH"' >> ~/.bashrc
fi

# === INSTALL PROJECT ===
echo ""
echo "[2/7] Extracting project..."
PROJECT_DIR="$HOME/quantpulse"
mkdir -p "$PROJECT_DIR"
cd "$PROJECT_DIR"

# If archive is in same directory, extract it
if [ -f "./quantpulse-complete-project.tar.gz" ]; then
  tar -xzf ./quantpulse-complete-project.tar.gz
  echo "Project extracted to $PROJECT_DIR"
else
  echo "Please place quantpulse-complete-project.tar.gz in this directory and re-run."
  exit 1
fi

# === INSTALL PYTHON DEPENDENCIES ===
echo ""
echo "[3/7] Installing Python dependencies..."
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip -q
pip install -r mini-services/trading-engine/requirements.txt -q

# Optional broker packages (uncomment what you need)
# pip install kiteconnect          # Zerodha
# pip install smartapi-python       # Angel One
# pip install fyers-apiv3           # Fyers
# pip install dhanhq                # Dhan
# pip install MetaTrader5           # MT5 (Windows only)
# pip install ib_insync             # Interactive Brokers

echo "Python dependencies installed."

# === INSTALL NODE DEPENDENCIES ===
echo ""
echo "[4/7] Installing Node.js dependencies..."
export PATH="$BUN_INSTALL/bin:$PATH"
bun install 2>/dev/null || npm install
export DATABASE_URL="file:./db/custom.db"
bun run db:generate
bun run build
echo "Node dependencies installed."

# === SETUP DATABASE ===
echo ""
echo "[5/7] Setting up database..."
export DATABASE_URL="file:./db/custom.db"
mkdir -p db
bun run db:deploy 2>/dev/null || bun run db:push
echo "Database initialized."

# === CREATE STARTUP SCRIPTS ===
echo ""
echo "[6/7] Creating startup scripts..."

# Python engine startup
cat > "$PROJECT_DIR/start-engine.sh" << 'EOF'
#!/bin/bash
cd "$(dirname "$0")"
source .venv/bin/activate
cd mini-services/trading-engine
exec python3 main.py
EOF
chmod +x start-engine.sh

# Next.js dashboard startup
cat > "$PROJECT_DIR/start-dashboard.sh" << 'EOF'
#!/bin/bash
cd "$(dirname "$0")"
export PATH="$HOME/.bun/bin:$PATH"
export NODE_ENV=production
export PORT=3000
export HOSTNAME=127.0.0.1
exec bun run start
EOF
chmod +x start-dashboard.sh

# Combined startup
cat > "$PROJECT_DIR/start-all.sh" << 'EOF'
#!/bin/bash
cd "$(dirname "$0")"
echo "Starting QuantPulse..."
# Start Python engine in background
./start-engine.sh &
ENGINE_PID=$!
echo "Trading Engine started (PID: $ENGINE_PID) on port 3030"
# Wait for engine
sleep 3
# Start Next.js dashboard
./start-dashboard.sh &
DASH_PID=$!
echo "Dashboard started (PID: $DASH_PID) on port 3000"
echo ""
echo "QuantPulse is running:"
echo "  Dashboard:      http://localhost:3000"
echo "  Trading Engine: http://localhost:3030"
echo "  Health:         http://localhost:3030/health"
echo ""
echo "Press Ctrl+C to stop both services."
trap "kill $ENGINE_PID $DASH_PID 2>/dev/null; exit" SIGINT SIGTERM
wait
EOF
chmod +x start-all.sh

# === CREATE SYSTEMD SERVICES (optional, for auto-restart) ===
echo ""
echo "[7/7] Creating systemd services (optional)..."

sudo tee /etc/systemd/system/quantpulse-engine.service > /dev/null << EOF
[Unit]
Description=QuantPulse Trading Engine
After=network.target

[Service]
Type=simple
User=$USER
WorkingDirectory=$PROJECT_DIR/mini-services/trading-engine
ExecStart=$PROJECT_DIR/.venv/bin/python3 main.py
Restart=always
RestartSec=5
EnvironmentFile=$PROJECT_DIR/.env
Environment=PYTHONPATH=$PROJECT_DIR/mini-services/trading-engine
Environment=ENGINE_HOST=127.0.0.1
Environment=TRADING_MODE=PAPER

[Install]
WantedBy=multi-user.target
EOF

sudo tee /etc/systemd/system/quantpulse-dashboard.service > /dev/null << EOF
[Unit]
Description=QuantPulse Dashboard
After=network.target quantpulse-engine.service

[Service]
Type=simple
User=$USER
WorkingDirectory=$PROJECT_DIR
ExecStart=$HOME/.bun/bin/bun run start
Restart=always
RestartSec=5
Environment=NODE_ENV=production
Environment=PORT=3000
Environment=HOSTNAME=127.0.0.1

[Install]
WantedBy=multi-user.target
EOF

echo ""
echo "================================================"
echo "  DEPLOYMENT COMPLETE!"
echo "================================================"
echo ""
echo "To start manually:"
echo "  cd $PROJECT_DIR"
echo "  ./start-all.sh"
echo ""
echo "To start as systemd service (auto-restart on crash):"
echo "  sudo systemctl daemon-reload"
echo "  sudo systemctl enable quantpulse-engine quantpulse-dashboard"
echo "  sudo systemctl start quantpulse-engine quantpulse-dashboard"
echo ""
echo "Check status:"
echo "  sudo systemctl status quantpulse-engine"
echo "  sudo systemctl status quantpulse-dashboard"
echo ""
echo "Dashboard will be available at:"
echo "  http://YOUR_VPS_IP:3000"
echo ""
echo "Trading Engine API at:"
echo "  http://YOUR_VPS_IP:3030/health"
echo ""
echo "Next steps:"
echo "  1. Open http://YOUR_VPS_IP:3000 in browser"
echo "  2. Go to Brokers tab → add Zerodha/MT5 credentials"
echo "  3. Go to JARVIS tab → Run Full Analysis"
echo "================================================"
