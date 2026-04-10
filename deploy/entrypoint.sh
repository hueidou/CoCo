#!/bin/sh
# Substitute COCO_PORT in supervisord template and start supervisord.
# Default port 8088; override at runtime with -e COCO_PORT=3000.
set -e
export COCO_PORT="${COCO_PORT:-8088}"
envsubst '${COCO_PORT}' \
  < /etc/supervisor/conf.d/supervisord.conf.template \
  > /etc/supervisor/conf.d/supervisord.conf
exec /usr/bin/supervisord -c /etc/supervisor/conf.d/supervisord.conf
