#!/bin/bash

echo "Installing RC Simulator service..."

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
sudo cp "${REPO_ROOT}/ops/linux/services/moza_udp_client.service" /etc/systemd/system/

sudo systemctl daemon-reload

sudo systemctl enable moza_udp_client.service

sudo systemctl restart moza_udp_client.service

echo "Service installed and restarted."