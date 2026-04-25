#!/bin/bash
# Auto-Trader Deployment Script for Oracle Cloud Free Tier (Ubuntu)
# Run: chmod +x setup.sh && ./setup.sh

set -e

echo "========================================"
echo "  Auto-Trader Deployment Setup"
echo "========================================"

# Update system
sudo apt update && sudo apt upgrade -y

# Install Python 3.11+ and pip
sudo apt install -y python3 python3-pip python3-venv git

# Clone repo (replace with your GitHub repo URL)
cd /home/ubuntu
if [ ! -d "auto-trader" ]; then
    git clone https://github.com/YOUR_USERNAME/auto-trader.git
fi
cd auto-trader

# Create virtual environment
python3 -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Create .env file (you'll need to edit this with your keys)
if [ ! -f ".env" ]; then
    cp .env.example .env
    echo ">>> IMPORTANT: Edit .env with your Alpaca API keys!"
    echo ">>> Run: nano /home/ubuntu/auto-trader/.env"
fi

# Create log directory
mkdir -p logs

# Install systemd services
sudo cp deploy/auto-trader.service /etc/systemd/system/
sudo cp deploy/dashboard.service /etc/systemd/system/

# Reload systemd and enable services
sudo systemctl daemon-reload
sudo systemctl enable auto-trader
sudo systemctl enable dashboard

# Start services
sudo systemctl start auto-trader
sudo systemctl start dashboard

echo "========================================"
echo "  Deployment Complete!"
echo "========================================"
echo ""
echo "  Bot status:       sudo systemctl status auto-trader"
echo "  Dashboard status:  sudo systemctl status dashboard"
echo "  Bot logs:          sudo journalctl -u auto-trader -f"
echo "  Dashboard logs:    sudo journalctl -u dashboard -f"
echo ""
echo "  Dashboard URL:     http://YOUR_VM_IP:8501"
echo ""
echo "  IMPORTANT: Open port 8501 in Oracle Cloud Security Rules!"
echo "========================================"
