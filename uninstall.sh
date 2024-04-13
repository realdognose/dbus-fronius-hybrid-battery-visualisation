#!/bin/bash

kill $(pgrep -f 'supervise dbus-fronius-hybrid-battery-visualisation')
chmod a-x /data/dbus-fronius-hybrid-battery-visualisation/service/run
svc -d /service/dbus-fronius-hybrid-battery-visualisation
./restart.sh
