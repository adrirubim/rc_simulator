#!/usr/bin/env bash
set -euo pipefail

print_usage() {
  cat <<'EOF'
GStreamer UDP H264 preview helper.

Usage:
  ops/linux/camera_receive.sh [--port PORT] [--fullscreen 0|1]

Defaults:
  --port 5600
  --fullscreen 0
EOF
}

VIDEO_PORT="5600"
FULLSCREEN="0"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --port)
      VIDEO_PORT="${2:-}"
      shift 2
      ;;
    --fullscreen)
      FULLSCREEN="${2:-0}"
      shift 2
      ;;
    -h|--help)
      print_usage
      exit 0
      ;;
    *)
      echo "Unknown argument: $1" >&2
      print_usage >&2
      exit 2
      ;;
  esac
done

if ! command -v gst-launch-1.0 >/dev/null 2>&1; then
  echo "Error: gst-launch-1.0 not found. Install gstreamer1.0-tools." >&2
  exit 2
fi

CAPS="application/x-rtp,media=video,encoding-name=H264,payload=96,clock-rate=90000"

if [[ "${FULLSCREEN}" == "1" ]]; then
  gst-launch-1.0 -v \
    "udpsrc port=${VIDEO_PORT} caps=${CAPS}" ! \
    rtph264depay ! h264parse ! avdec_h264 ! videoconvert ! videoflip method=rotate-180 ! \
    waylandsink fullscreen=true sync=false
else
  gst-launch-1.0 -v \
    "udpsrc port=${VIDEO_PORT} caps=${CAPS}" ! \
    rtph264depay ! h264parse ! avdec_h264 ! videoconvert ! videoflip method=rotate-180 ! \
    autovideosink sync=false
fi