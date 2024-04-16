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
from dbus.mainloop.glib import DBusGMainLoop
import dbus
 
# our own packages from victron
sys.path.insert(1, os.path.join(os.path.dirname(__file__), '/opt/victronenergy/dbus-systemcalc-py/ext/velib_python'))
from vedbus import VeDbusService

class SystemBus(dbus.bus.BusConnection):
    def __new__(cls):
        return dbus.bus.BusConnection.__new__(cls, dbus.bus.BusConnection.TYPE_SYSTEM)

class SessionBus(dbus.bus.BusConnection):
    def __new__(cls):
        return dbus.bus.BusConnection.__new__(cls, dbus.bus.BusConnection.TYPE_SESSION)
    
def dbusconnection():
    return SessionBus() if 'DBUS_SESSION_BUS_ADDRESS' in os.environ else SystemBus()

class DbusFroniusHybridService:
  def __init__(self, 
               serviceNamePVInverter, serviceNameBattery, 
               pathsPVInverter, pathsBattery, 
               productnamePVInverter='Fronius Hybrid', ProducnameBattery='Fronius Hybrid Attached Battery', 
               connection='Fronius meter JSON API'):
    
    config = configparser.ConfigParser()
    config.read("%s/config.ini" % (os.path.dirname(os.path.realpath(__file__))))

    deviceinstancePVInterter = int(config['ONPREMISE']['DeviceIdForPVInverter'])
    deviceinstanceBattery = int(config['ONPREMISE']['DeviceIdForBattery'])

    self._dbusservicePVInverter = VeDbusService("{}.http_{:02d}".format(serviceNamePVInverter, deviceinstancePVInterter), bus=dbusconnection())
    self._dbusservicePVInverterBattery = VeDbusService("{}.http_{:02d}".format(serviceNameBattery, deviceinstanceBattery), bus=dbusconnection())
     
    # Create the management objects, as specified in the ccgx dbus-api document
    self._dbusservicePVInverter.add_path('/Mgmt/ProcessName', __file__)
    self._dbusservicePVInverter.add_path('/Mgmt/ProcessVersion', 'Unkown version, and running on Python ' + platform.python_version())
    self._dbusservicePVInverter.add_path('/Mgmt/Connection', connection)
 
    # Create the mandatory objects
    self._dbusservicePVInverter.add_path('/DeviceInstance', deviceinstancePVInterter)
    self._dbusservicePVInverter.add_path('/ProductId', 0xa142) # See https://gist.github.com/seidler2547/52f3e91cbcbf2fa257ae79371bb78588, 41282 Fronius solar inverter
    self._dbusservicePVInverter.add_path('/ProductName', productnamePVInverter) 
    self._dbusservicePVInverter.add_path('/Latency', None)    
    self._dbusservicePVInverter.add_path('/FirmwareVersion', 0.1)
    self._dbusservicePVInverter.add_path('/HardwareVersion', 0)
    self._dbusservicePVInverter.add_path('/Connected', 1)
    self._dbusservicePVInverter.add_path('/Position', int(config['ONPREMISE']['PVInverterPosition'])) 
    self._dbusservicePVInverter.add_path('/Serial', self._getFronisSerial())
    self._dbusservicePVInverter.add_path('/UpdateIndex', 0)

    # Create the management objects, as specified in the ccgx dbus-api document
    self._dbusservicePVInverterBattery.add_path('/Mgmt/ProcessName', __file__)
    self._dbusservicePVInverterBattery.add_path('/Mgmt/ProcessVersion', 'Unkown version, and running on Python ' + platform.python_version())
    self._dbusservicePVInverterBattery.add_path('/Mgmt/Connection', connection)
 
    # Create the mandatory objects
    bat_detail_data = self._getFroniusBatteryDetailData()
    vendor = bat_detail_data['Body']['Data']["Controller"]["Details"]["Manufacturer"]
    model = bat_detail_data['Body']['Data']["Controller"]["Details"]["Model"]
    size = bat_detail_data['Body']['Data']["Controller"]["DesignedCapacity"]
    
    self._dbusservicePVInverterBattery.add_path('/ProductName', "[" + vendor  +"] " +  model + " " + str(round(size/1000, 1)))
    self._dbusservicePVInverterBattery.add_path('/DeviceInstance', deviceinstanceBattery)
    self._dbusservicePVInverterBattery.add_path('/ProductId', 57344) 
    self._dbusservicePVInverterBattery.add_path('/Latency', None)    
    self._dbusservicePVInverterBattery.add_path('/FirmwareVersion', 0.1)
    self._dbusservicePVInverterBattery.add_path('/HardwareVersion', 0)
    self._dbusservicePVInverterBattery.add_path('/Connected', 1)
    self._dbusservicePVInverterBattery.add_path('/Serial', self._getFronisSerial())
    self._dbusservicePVInverterBattery.add_path('/UpdateIndex', 0)

    # add path values to dbus
    for path, settings in pathsPVInverter.items():
      self._dbusservicePVInverter.add_path(
        path, settings['initial'], gettextcallback=settings['textformat'], writeable=True, onchangecallback=self._handlechangedvalue)

    for path, settings in pathsBattery.items():
      self._dbusservicePVInverterBattery.add_path(
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
    return config
  
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
  
  def _getFroniusBatteryDetailDataUrl(self):
    config = self._getConfig()
    accessType = config['DEFAULT']['AccessType']
    
    if accessType == 'OnPremise': 
        URL = "http://%s/solar_api/v1/GetStorageRealtimeData.cgi?Scope=Device&DeviceId=0" % (config['ONPREMISE']['Host'])
    else:
        raise ValueError("AccessType %s is not supported" % (config['DEFAULT']['AccessType']))
    
    return URL
  
  def _getFroniusPVDataUrl(self):
    config = self._getConfig()
    accessType = config['DEFAULT']['AccessType']
    
    if accessType == 'OnPremise': 
        URL = "http://%s/solar_api/v1/GetInverterRealtimeData.cgi?Scope=Device&DataCollection=CommonInverterData&DeviceId=%s" % (config['ONPREMISE']['Host'], config['ONPREMISE']['HybridID'])
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
  
  def _getFroniusBatteryDetailData(self):
    URL = self._getFroniusBatteryDetailDataUrl()
    meter_r = requests.get(url = URL)
    
    # check for response
    if not meter_r:
        raise ConnectionError("No response from Fronius - %s" % (URL))
    
    meter_data = meter_r.json()     
    
    # check for Json
    if not meter_data:
        raise ValueError("Converting response to JSON failed on Fronius")
    
    return meter_data
  
  def _getFroniusPVData(self):
    URL = self._getFroniusPVDataUrl()
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
    logging.info("--- End: sign of life ---")
    return True
 
  def _update(self):   
    try:
       #get data from Fronius
       bat_data = self._getFroniusBatteryData()
       bat_detail_data = self._getFroniusBatteryDetailData()
       pv_data = self._getFroniusPVData()

       #gather data
       soc = bat_detail_data['Body']['Data']["Controller"]["StateOfCharge_Relative"]
       temp = bat_detail_data['Body']['Data']["Controller"]["Temperature_Cell"]
       u_bat = bat_detail_data['Body']['Data']["Controller"]["Voltage_DC"]
       i_bat = bat_detail_data['Body']['Data']["Controller"]["Current_DC"]

       p_bat = bat_data['Body']['Data']["Site"]["P_Akku"]
       p_load = bat_data['Body']['Data']["Site"]["P_Load"]
       p_pv_grid = bat_data['Body']['Data']["Site"]["P_PV"]

       u_pv = pv_data['Body']['Data']['UAC']['Value']
       i_pv = pv_data['Body']['Data']['IAC']['Value']
       p_pv = pv_data['Body']['Data']['PAC']['Value']
       f_pv = pv_data['Body']['Data']['FAC']['Value']
       p_pv_total = pv_data['Body']['Data']['TOTAL_ENERGY']['Value'] / 1000.0

       #Act as regular inverter on DBUS for Solar-Production ob dbusservice.
       #Act as AC-Generator on dbusservice2
       self._dbusservicePVInverter['/Ac/Energy/Forward'] = p_pv_total
       self._dbusservicePVInverter['/Ac/L1/Voltage'] = u_pv
       self._dbusservicePVInverter['/Ac/L2/Voltage'] = u_pv
       self._dbusservicePVInverter['/Ac/L3/Voltage'] = u_pv

       self._dbusservicePVInverterBattery['/Dc/0/Power'] = i_bat * u_bat
       self._dbusservicePVInverterBattery['/Dc/0/Current'] = i_bat
       self._dbusservicePVInverterBattery['/Dc/0/Voltage'] = u_bat
       self._dbusservicePVInverterBattery['/Temperature'] = temp
       self._dbusservicePVInverterBattery['/Soc'] = soc

       #battery is discharging, no PV available.
       self._dbusservicePVInverter['/Ac/Power'] = p_pv
       self._dbusservicePVInverter['/Ac/L1/Power'] = (p_pv)/3
       self._dbusservicePVInverter['/Ac/L2/Power'] = (p_pv)/3
       self._dbusservicePVInverter['/Ac/L3/Power'] = (p_pv)/3
       self._dbusservicePVInverter['/Ac/L1/Current'] = i_pv/3 
       self._dbusservicePVInverter['/Ac/L2/Current'] = i_pv/3 
       self._dbusservicePVInverter['/Ac/L3/Current'] = i_pv/3 

       self._dbusserviceInverter['/Dc/0/Voltage'] = u_bat
       self._dbusserviceInverter['/Ac/Out/L1/V'] = u_pv
       self._dbusserviceInverter['/Ac/Out/L1/I'] = i_pv
       self._dbusserviceInverter['/Ac/Out/L1/P'] = p_bat

       # increment UpdateIndex - to show that new data is available
       index = self._dbusservicePVInverter['/UpdateIndex'] + 1  # increment index
       index2 = self._dbusservicePVInverterBattery['/UpdateIndex'] + 1  # increment index
       
       if index > 255:   # maximum value of the index
         index = 0       # overflow from 255 to 0

       if index2 > 255:   # maximum value of the index
         index2 = 0       # overflow from 255 to 0
       
       self._dbusservicePVInverter['/UpdateIndex'] = index
       self._dbusservicePVInverterBattery['/UpdateIndex'] = index2

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
                            level=logging.WARN,
                            handlers=[
                                logging.FileHandler("%s/current.log" % (os.path.dirname(os.path.realpath(__file__)))),
                                logging.StreamHandler()
                            ])
 
  try:
      from dbus.mainloop.glib import DBusGMainLoop
      # Have a mainloop, so we can send/receive asynchronous calls to and from dbus
      DBusGMainLoop(set_as_default=True)
     
      #formatting 
      _kwh = lambda p, v: (str(round(v, 2)) + ' kWh')
      _a = lambda p, v: (str(round(v, 1)) + ' A')
      _w = lambda p, v: (str(round(v, 1)) + ' W')
      _v = lambda p, v: (str(round(v, 1)) + ' V')   
      _p = lambda p, v: (str(v))
      _t = lambda p, v: (str(round(v, 1)) + ' °C')   


      #3rd Service, Inverter is experimental. 
      serviceNamePVInverter = "com.victronenergy.pvinverter"
      serviceNameBattery = "com.victronenergy.battery"

      #start our services
      pvac_output = DbusFroniusHybridService(
        serviceNamePVInverter=serviceNamePVInverter,
        serviceNameBattery=serviceNameBattery,
        pathsPVInverter={
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
        pathsBattery={
          '/Dc/0/Voltage': {'initial': 0, 'textformat': _v},
          '/Dc/0/Current': {'initial': 0, 'textformat': _a},
          '/Dc/0/Power': {'initial': 0, 'textformat': _w},
          '/Soc': {'initial': 0, 'textformat': _p},
          '/Temperature': {'initial': 0, 'textformat': _t},
        })
     
      logging.info('Connected to dbus, and switching over to gobject.MainLoop() (= event based)')
      mainloop = gobject.MainLoop()
      mainloop.run()            
  except Exception as e:
    logging.critical('Error at %s', 'main', exc_info=e)
if __name__ == "__main__":
  main()
