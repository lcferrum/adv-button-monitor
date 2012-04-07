#!/bin/sh
if [ "$USER" != "root" ]; then
  echo must be run as root
  exit 1
fi

/bin/develsh -c "
  source /etc/profile
  PATH=$PATH:/usr/local/bin
  python /opt/n9-button-monitor/n9-button-monitor.py
"