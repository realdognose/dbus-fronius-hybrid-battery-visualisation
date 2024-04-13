# dbus-fronius-hybrid-battery-visualisation

TODO

# Installation.

```
wget https://github.com/realdognose/dbus-fronius-hybrid-battery-visualisation/archive/refs/heads/main.zip
unzip main.zip "dbus-fronius-hybrid-battery-visualisation-main/*" -d /data
mv /data/dbus-fronius-hybrid-battery-visualisation-main /data/dbus-fronius-hybrid-battery-visualisation
chmod a+x /data/dbus-fronius-hybrid-battery-visualisation/install.sh
/data/dbus-fronius-hybrid-battery-visualisation/install.sh
rm main.zip
```
⚠️ Check configuration after that - because service is already installed an running and with wrong connection data (host, username, pwd) you will spam the log-file
### Stop service
```
svc -d /service/dbus-fronius-hybrid-battery-visualisation
```
### Start service
```
svc -u /service/dbus-fronius-hybrid-battery-visualisation
```
### Reload data
```
/data/dbus-fronius-hybrid-battery-visualisation/restart.sh
```
### View log file
```
cat /data/dbus-fronius-hybrid-battery-visualisation/current.log
```
### Change config.ini
Within the project there is a file `/data/dbus-fronius-hybrid-battery-visualisation/config.ini` - just change the values - most important is the host and hostPlug in section "ONPREMISE". More details below:

Afther change the config file execute restart.sh to reload new settings 

| Section  | Config vlaue | Explanation |
| ------------- | ------------- | ------------- |
| DEFAULT  | AccessType | Fixed value 'OnPremise' |
| DEFAULT  | SignOfLifeLog  | Time in minutes how often a status is added to the log-file `current.log` with log-level INFO |
| ONPREMISE  | Host | IP or hostname of on-premise Fronis Meter web-interface |
| ONPREMISE  | MeterID  | Your meter ID
| ONPREMISE  | intervalMs  | Interval time in ms to get data from Fronius
| ONPREMISE  | HostPlug  | IP of the shelly plug. Currently only unprotected http-access supported.
---

# original description

forked from: smart meter readout repository at: 
https://github.com/ayasystems/dbus-fronius-smart-meter