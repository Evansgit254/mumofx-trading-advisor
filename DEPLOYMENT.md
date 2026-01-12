# Deployment Guide: TradingExpert (Dockerized)

This guide walks you through deploying the **TradingExpert V15.0** system on a remote Virtual Private Server (VPS) using Docker. This ensures the bot runs 24/7 with automatic restarts and reliable logging.

## Prerequisites

- **VPS**: A distinct server (e.g., DigitalOcean Droplet, AWS EC2, Linode).
  - **OS**: Ubuntu 22.04 LTS or newer recommended.
  - **Specs**: Minimum 1GB RAM (2GB recommended), 1 vCPU.
- **Git**: Installed on the VPS.
- **Docker & Docker Compose**: Installed on the VPS.

## Step 1: Server Setup (One-Time)

SSH into your VPS:
```bash
ssh root@your_vps_ip
```

Install Docker and Git:
```bash
sudo apt update
sudo apt install -y git docker.io docker-compose-plugin
```
*Note: If `docker-compose-plugin` is not found, verify you are on Ubuntu 20.04+. Alternatively, install the simplified package `sudo apt install docker-compose` and use `docker-compose` (with a hyphen) instead of `docker compose` in all commands.*

## Step 2: Clone the Repository

Clone your project from GitHub:
```bash
git clone https://github.com/your-repo/TradingExpert.git
cd TradingExpert
```

## Step 3: Configure Environment

Create your production `.env` file. You can use `nano` to paste your secrets:
```bash
nano .env
```

**Paste the following (filled with your keys):**
```env
TELEGRAM_BOT_TOKEN=your_token_here
TELEGRAM_CHAT_ID=your_chat_id_here
GEMINI_API_KEY=your_gemini_key_here
GITHUB_ACTIONS=false
```
*Press `Ctrl+X`, then `Y`, then `Enter` to save.*

## Step 4: Build and Run

Run the container in detached mode (background):
```bash
docker compose up -d --build
```

### Verification
Check if the container is running:
```bash
docker compose ps
```

View live logs to ensure it's trading:
```bash
docker compose logs -f
```

## Maintenance

### Updating the Bot
When you push new code to GitHub, update the VPS:
```bash
git pull origin main
docker compose up -d --build
```
*This will rebuild the container with new code and restart it seamlessly.*

### Stopping
```bash
docker compose down
```

## Data Persistence
- **Database**: `database/signals.db` is persisted in the local `database/` folder on the host.
- **Logs**: stored in `logs/`.
- **Outputs**: stored in `outputs/`.

This setup is resilient. If the server reboots or the bot crashes, Docker will automatically restart the service (`restart: unless-stopped` policy).
