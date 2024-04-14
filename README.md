# dbus-fronius-hybrid-battery-visualisation

The original Implementation of Victrons Fronius Readout shows all Fronius inverters as PV-Inverters. With a Fronius Hybrid including a battery, the energey coming
from the battery is simply shown as PV-Output. I'm running Victron ESS as kind of a subgrid in my home and the fact that PV-Power is available during night (which is 
actually the Fronius-Hybrids Battery discharge) lead to all sorts of strange behaviour of the ess: Not discharging it's own battery, sometimes even charging from the 
Fronius battery, because ESS thinks that is available PV-Power. 

So, I wrote my Own script, that addresses two issues: 

- The Fronius Hybrid Inverters PV Output will now be shown as it's regular PV Output MINUS Battery charge. (That is PV-Input we don't have available to ESS)
- When the Fronius is Discharging, it's AC Output will show 0, so the ESS starts to behave correctly with the knownledge that there is no PV-Power.
  (For another hack required to have ESS operate 100% correctly, also see my repository at: https://github.com/realdognose/dbus-fronius-smart-meter-with-phase1-injection)
- Now, the victron system will miss the AC-Loads - so, i've added a genset called "Fronius Hybrid attached Battery" that will show the actual discharge amount.
  When running with AC1 set to grid, the generator won't be displayed in VRM, but it is taken into account for total AC-load calculation. 

Views while charging the battery: 

![image](https://github.com/realdognose/dbus-fronius-hybrid-battery-visualisation/blob/main/img/deviceViewCharging.jpg)

![image](https://github.com/realdognose/dbus-fronius-hybrid-battery-visualisation/blob/main/img/VRM_Charging.png)
Note that the PV Power in VRM now doesn't contain energy that is directly send to the Fronius attached battery.

View while discharging battery:

![image](https://github.com/realdognose/dbus-fronius-hybrid-battery-visualisation/blob/main/img/DeviceViewDischarge.png)

![image](https://github.com/realdognose/dbus-fronius-hybrid-battery-visualisation/blob/main/img/VRM_Discharge.png) 
VRM is not showing the generator, but the AC Load is calculated correctly. 

# Script Installation.

```
wget https://github.com/realdognose/dbus-fronius-hybrid-battery-visualisation/archive/refs/heads/main.zip
unzip main.zip "dbus-fronius-hybrid-battery-visualisation-main/*" -d /data
mv /data/dbus-fronius-hybrid-battery-visualisation-main /data/dbus-fronius-hybrid-battery-visualisation
chmod a+x /data/dbus-fronius-hybrid-battery-visualisation/install.sh
/data/dbus-fronius-hybrid-battery-visualisation/install.sh
rm main.zip
```

⚠️ Check configuration after that - because service is already installed an running and with wrong connection data you will spam the log-file
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
Within the project there is a file `/data/dbus-fronius-hybrid-battery-visualisation/config.ini` - just change the values - most important is the host and HybridID in section "ONPREMISE". More details bellow
and comments in the config file:

Afther change the config file execute restart.sh to reload new settings 

| Section  | Config vlaue | Explanation |
| ------------- | ------------- | ------------- |
| DEFAULT  | AccessType | Fixed value 'OnPremise' |
| DEFAULT  | SignOfLifeLog  | Time in minutes how often a status is added to the log-file `current.log` with log-level INFO |
| ONPREMISE  | Host | IP or hostname of on-premise Fronis Meter web-interface |
| ONPREMISE  | HybridID  | Your HybridDevice ID
| ONPREMISE  | intervalMs  | Interval time in ms to get data from Fronius
---

# original description

forked from: smart meter readout repository at: 
https://github.com/ayasystems/dbus-fronius-smart-meter

for another hacky solution around running ESS as subgrid, see 
https://github.com/realdognose/dbus-fronius-smart-meter-with-phase1-injection
