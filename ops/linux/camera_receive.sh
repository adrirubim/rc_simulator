#!/bin/bash

VIDEO_PORT="${1:-5600}"
FULLSCREEN="${2:-0}"

if [ "$FULLSCREEN" = "1" ]; then
    gst-launch-1.0 -v \
    udpsrc port=${VIDEO_PORT} caps="application/x-rtp,media=video,encoding-name=H264,payload=96,clock-rate=90000" ! \
    rtph264depay ! h264parse ! avdec_h264 ! videoconvert ! videoflip method=rotate-180 ! \
    waylandsink fullscreen=true sync=false
else
    gst-launch-1.0 -v \
    udpsrc port=${VIDEO_PORT} caps="application/x-rtp,media=video,encoding-name=H264,payload=96,clock-rate=90000" ! \
    rtph264depay ! h264parse ! avdec_h264 ! videoconvert ! videoflip method=rotate-180 ! \
    autovideosink sync=false
fi