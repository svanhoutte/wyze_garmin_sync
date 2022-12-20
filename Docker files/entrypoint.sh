#!/bin/bash
printenv > /etc/environment
printenv
/bin/bash ./connect_sync.sh
cron -f
