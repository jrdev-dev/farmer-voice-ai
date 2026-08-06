#!/usr/bin/env bash
# exit on error
set -o errexit

echo "=========================================="
echo "Setting up Farmer Voice AI on Oracle Cloud"
echo "=========================================="

# 1. Update system packages
echo "Updating system packages..."
sudo apt-get update -y

# 2. Install Docker if it's not installed
if ! command -v docker &> /dev/null
then
    echo "Installing Docker..."
    sudo apt-get install -y apt-transport-https ca-certificates curl software-properties-common
    curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo gpg --dearmor -o /usr/share/keyrings/docker-archive-keyring.gpg
    echo "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/docker-archive-keyring.gpg] https://download.docker.com/linux/ubuntu $(lsb_release -cs) stable" | sudo tee /etc/apt/sources.list.d/docker.list > /dev/null
    sudo apt-get update -y
    sudo apt-get install -y docker-ce docker-ce-cli containerd.io docker-compose-plugin
else
    echo "Docker is already installed."
fi

# 3. Add current user to docker group (so we don't need sudo docker)
sudo usermod -aG docker $USER

# 4. Create empty database and media files if they don't exist to prevent Docker from creating directories instead of files
touch backend/db.sqlite3
mkdir -p backend/media
# Fix permissions for the Docker user (user id 1000)
sudo chown -R 1000:1000 backend/db.sqlite3 backend/media

# 5. Build and start the Docker containers using the V2 compose command
echo "Building and starting the Docker containers..."
sudo docker compose up -d --build

echo "=========================================="
echo "Deployment Complete!"
echo "Your app should now be running on port 80."
echo "If you cannot access it, ensure Port 80 is open in Oracle Cloud VCN Security Lists."
echo "=========================================="
