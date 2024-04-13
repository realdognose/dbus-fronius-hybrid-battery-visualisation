#!/usr/bin/env python
 
# import normal packages
# https://github.com/victronenergy/dbus_modbustcp/blob/master/attributes.csv
import platform 
import logging
import sys
import os
import sys
if sys.version_info.major == 2:
    import gobject
else:
    from gi.repository import GLib as gobject
import sys
import time
import requests # for http GET
import configparser # for config/ini file
 
# our own packages from victron
sys.path.insert(1, os.path.join(os.path.dirname(__file__), '/opt/victronenergy/dbus-systemcalc-py/ext/velib_python'))
from vedbus import VeDbusService


class DbusFroniusHybridService:
  def __init__(self, servicename, servicename2, paths, paths2, 
               productname='Fronius Hybrid', connection='Fronius meter JSON API', productname2='Fronius attached Battery', connection2='Fronius meter JSON API'):
    
    config = configparser.ConfigParser()
    config.read("%s/config.ini" % (os.path.dirname(os.path.realpath(__file__))))

    deviceinstance = config['ONPREMISE']['DeviceIdForInverter']
    deviceinstance2 = config['ONPREMISE']['DeviceIdForGenSet']

    self._dbusservice = VeDbusService("{}.http_{:02d}".format(servicename, deviceinstance))
    self._dbusservice2 = VeDbusService("{}.http_{:02d}".format(servicename2, deviceinstance2))
    self._paths = paths
    self._paths2 = paths2
 
    logging.debug("%s /DeviceInstance = %d" % (servicename, deviceinstance))
    logging.debug("%s /DeviceInstance = %d" % (servicename2, deviceinstance2))
 
    # Create the management objects, as specified in the ccgx dbus-api document
    self._dbusservice.add_path('/Mgmt/ProcessName', __file__)
    self._dbusservice.add_path('/Mgmt/ProcessVersion', 'Unkown version, and running on Python ' + platform.python_version())
    self._dbusservice.add_path('/Mgmt/Connection', connection)
 
    # Create the mandatory objects
    self._dbusservice.add_path('/DeviceInstance', deviceinstance)
    self._dbusservice.add_path('/ProductId', 0xa142) # See https://gist.github.com/seidler2547/52f3e91cbcbf2fa257ae79371bb78588, 41282 Fronius solar inverter
    self._dbusservice.add_path('/ProductName', productname)
    self._dbusservice.add_path('/CustomName', "Fronius Hybrid")    
    self._dbusservice.add_path('/Latency', None)    
    self._dbusservice.add_path('/FirmwareVersion', 0.1)
    self._dbusservice.add_path('/HardwareVersion', 0)
    self._dbusservice.add_path('/Connected', 1)
    self._dbusservice.add_path('/Position', 1) # normaly only needed for pvinverter
    self._dbusservice.add_path('/Serial', self._getFronisSerial())
    self._dbusservice.add_path('/UpdateIndex', 0)
 
    # Create the management objects, as specified in the ccgx dbus-api document
    self._dbusservice2.add_path('/Mgmt/ProcessName', __file__)
    self._dbusservice2.add_path('/Mgmt/ProcessVersion', 'Unkown version, and running on Python ' + platform.python_version())
    self._dbusservice2.add_path('/Mgmt/Connection', connection2)
 
    # Create the mandatory objects
    self._dbusservice2.add_path('/DeviceInstance', deviceinstance2)
    self._dbusservice2.add_path('/ProductId', 0xb040)  #Using the id for a Fischer Panda Genset
    self._dbusservice2.add_path('/ProductName', productname2)
    self._dbusservice2.add_path('/CustomName', "Fronius Hybrid attached Battery")    
    self._dbusservice2.add_path('/Latency', None)    
    self._dbusservice2.add_path('/FirmwareVersion', 0.1)
    self._dbusservice2.add_path('/HardwareVersion', 0)
    self._dbusservice2.add_path('/Connected', 1)
    self._dbusservice2.add_path('/Serial', self._getFronisSerial())

    # add path values to dbus
    for path, settings in self._paths.items():
      self._dbusservice.add_path(
        path, settings['initial'], gettextcallback=settings['textformat'], writeable=True, onchangecallback=self._handlechangedvalue)
 
    for path, settings in self._paths2.items():
      self._dbusservice2.add_path(
        path, settings['initial'], gettextcallback=settings['textformat'], writeable=True, onchangecallback=self._handlechangedvalue)

    # last update
    self._lastUpdate = 0
 
    # add _update function 'timer'
    gobject.timeout_add(int(config['ONPREMISE']['intervalMs']), self._update) # pause 250ms before the next request
    
    # add _signOfLife 'timer' to get feedback in log every 5minutes
    gobject.timeout_add(self._getSignOfLifeInterval()*60*1000, self._signOfLife)

  def _getFronisSerial(self):
    return "0815"
  
  def _getConfig(self):
    config = configparser.ConfigParser()
    config.read("%s/config.ini" % (os.path.dirname(os.path.realpath(__file__))))
    return config;
  
  def _getSignOfLifeInterval(self):
    config = self._getConfig()
    value = config['DEFAULT']['SignOfLifeLog']
    
    if not value: 
        value = 0
    
    return int(value)
 
  def _getFroniusBatteryDataUrl(self):
    config = self._getConfig()
    accessType = config['DEFAULT']['AccessType']
    
    if accessType == 'OnPremise': 
        URL = "http://%s/solar_api/v1/GetPowerFlowRealtimeData.fcgi" % (config['ONPREMISE']['Host'])
    else:
        raise ValueError("AccessType %s is not supported" % (config['DEFAULT']['AccessType']))
    
    return URL
 
  def _getFroniusBatteryData(self):
    URL = self._getFroniusBatteryDataUrl()
    meter_r = requests.get(url = URL)
    
    # check for response
    if not meter_r:
        raise ConnectionError("No response from Fronius - %s" % (URL))
    
    meter_data = meter_r.json()     
    
    # check for Json
    if not meter_data:
        raise ValueError("Converting response to JSON failed on Fronius")
    
    return meter_data
 
  def _signOfLife(self):
    logging.info("--- Start: sign of life ---")
    logging.info("Last _update() call: %s" % (self._lastUpdate))
    logging.info("Last '/Ac/Power': %s" % (self._dbusservice['/Ac/Power']))
    logging.info("--- End: sign of life ---")
    return True
 
  def _update(self):   
    try:
       #get data from Fronius
       bat_data = self._getFroniusBatteryData()

       #gather data
       p_bat = bat_data['Body']['Data']["Site"]["P_Akku"]
       p_load = bat_data['Body']['Data']["Site"]["P_Load"]
       p_pv = bat_data['Body']['Data']["Site"]["P_PV"]

       #Act as regular inverter on DBUS for Solar-Production ob dbusservice.
       #Act as AC-Generator on dbusservice2
       if (p_bat > 0):
         self._dbusservice['/Ac/Power'] = 0 #no PV Power.
         self._dbusservice['/Ac/L1/Power'] = 0 #no PV Power.
         self._dbusservice['/Ac/L2/Power'] = 0 #no PV Power.
         self._dbusservice['/Ac/L3/Power'] = 0 #no PV Power.
         self._dbusservice2['/Ac/Power'] =  (p_load * -1) #Pretend our generator is running. Use P_Load *-1 as this equals the AC load.
         self._dbusservice2['/Ac/L1/Power'] = (p_load * -1)/3 #Pretend our generator is running.
         self._dbusservice2['/Ac/L2/Power'] = (p_load * -1)/3 #Pretend our generator is running.
         self._dbusservice2['/Ac/L3/Power'] = (p_load * -1)/3 #Pretend our generator is running.
       
       # increment UpdateIndex - to show that new data is available
       index = self._dbusservice['/UpdateIndex'] + 1  # increment index
       index2 = self._dbusservice2['/UpdateIndex'] + 1  # increment index
       
       if index > 255:   # maximum value of the index
         index = 0       # overflow from 255 to 0

       if index2 > 255:   # maximum value of the index
         index2 = 0       # overflow from 255 to 0
       
       self._dbusservice['/UpdateIndex'] = index
       self._dbusservice2['/UpdateIndex'] = index2

       #update lastupdate vars
       self._lastUpdate = time.time()              
    except Exception as e:
       logging.critical('Error at %s', '_update', exc_info=e)
       
    # return true, otherwise add_timeout will be removed from GObject - see docs http://library.isr.ist.utl.pt/docs/pygtk2reference/gobject-functions.html#function-gobject--timeout-add
    return True
 
  def _handlechangedvalue(self, path, value):
    logging.critical("someone else updated %s to %s" % (path, value))
    return True # accept the change
 


def main():
  #configure logging
  logging.basicConfig(      format='%(asctime)s,%(msecs)d %(name)s %(levelname)s %(message)s',
                            datefmt='%Y-%m-%d %H:%M:%S',
                            level=logging.DEBUG,
                            handlers=[
                                logging.FileHandler("%s/current.log" % (os.path.dirname(os.path.realpath(__file__)))),
                                logging.StreamHandler()
                            ])
 
  try:
      from dbus.mainloop.glib import DBusGMainLoop
      # Have a mainloop, so we can send/receive asynchronous calls to and from dbus
      DBusGMainLoop(set_as_default=True)
     
      #formatting 
      _kwh = lambda p, v: (str(round(v, 2)) + ' KWh')
      _a = lambda p, v: (str(round(v, 1)) + ' A')
      _w = lambda p, v: (str(round(v, 1)) + ' W')
      _v = lambda p, v: (str(round(v, 1)) + ' V')   

      serviceNameInverter = "com.victronenergy.pvinverter"
      serviceNameGenerator = "com.victronenergy.genset"
      
      #start our services
      pvac_output = DbusFroniusHybridService(
        servicename=serviceNameInverter,
        servicename2=serviceNameGenerator,
        paths={
          '/Ac/Energy/Forward': {'initial': None, 'textformat': _kwh}, # energy produced by pv inverter
          '/Ac/Power': {'initial': 0, 'textformat': _w},
          '/Ac/L1/Voltage': {'initial': 0, 'textformat': _v},
          '/Ac/L2/Voltage': {'initial': 0, 'textformat': _v},
          '/Ac/L3/Voltage': {'initial': 0, 'textformat': _v},
          '/Ac/L1/Current': {'initial': 0, 'textformat': _a},
          '/Ac/L2/Current': {'initial': 0, 'textformat': _a},
          '/Ac/L3/Current': {'initial': 0, 'textformat': _a},
          '/Ac/L1/Power': {'initial': 0, 'textformat': _w},
          '/Ac/L2/Power': {'initial': 0, 'textformat': _w},
          '/Ac/L3/Power': {'initial': 0, 'textformat': _w},
          '/Ac/L1/Energy/Forward': {'initial': None, 'textformat': _kwh},
          '/Ac/L2/Energy/Forward': {'initial': None, 'textformat': _kwh},
          '/Ac/L3/Energy/Forward': {'initial': None, 'textformat': _kwh}
        },
        paths2={
          '/Ac/Power': {'initial': 0, 'textformat': _w},              #<- W    - total of all phases, real power

          '/Ac/L1/Current':{'initial': 0, 'textformat': _a},         #<- A AC
          '/Ac/L1/Power': {'initial': 0, 'textformat': _w},           #<- W, real power
          '/Ac/L1/Voltage': {'initial': 0, 'textformat': _v},         #<- V AC
          
          '/Ac/L2/Current':{'initial': 0, 'textformat': _a},         #<- A AC
          '/Ac/L2/Power': {'initial': 0, 'textformat': _w},           #<- W, real power
          '/Ac/L2/Voltage': {'initial': 0, 'textformat': _v},         #<- V AC

          '/Ac/L3/Current':{'initial': 0, 'textformat': _a},         #<- A AC
          '/Ac/L3/Power': {'initial': 0, 'textformat': _w},           #<- W, real power
          '/Ac/L3/Voltage': {'initial': 0, 'textformat': _v}         #<- V AC
        })
     
      logging.info('Connected to dbus, and switching over to gobject.MainLoop() (= event based)')
      mainloop = gobject.MainLoop()
      mainloop.run()            
  except Exception as e:
    logging.critical('Error at %s', 'main', exc_info=e)
if __name__ == "__main__":
  main()
