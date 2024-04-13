#!/bin/bash

# set permissions for script files
chmod a+x /data/dbus-fronius-hybrid-battery-visualisation/restart.sh
chmod 744 /data/dbus-fronius-hybrid-battery-visualisation/restart.sh

chmod a+x /data/dbus-fronius-hybrid-battery-visualisation/uninstall.sh
chmod 744 /data/dbus-fronius-hybrid-battery-visualisation/uninstall.sh

chmod a+x /data/dbus-fronius-hybrid-battery-visualisation/service/run
chmod 755 /data/dbus-fronius-hybrid-battery-visualisation/service/run

# create sym-link to run script in deamon
ln -s /data/dbus-fronius-hybrid-battery-visualisation/service /service/dbus-fronius-hybrid-battery-visualisation

# add install-script to rc.local to be ready for firmware update
filename=/data/rc.local
if [ ! -f $filename ]
then
    touch $filename
    chmod 755 $filename
    echo "#!/bin/bash" >> $filename
    echo >> $filename
fi

grep -qxF '/data/dbus-fronius-hybrid-battery-visualisation/install.sh' $filename || echo '/data/dbus-fronius-hybrid-battery-visualisation/install.sh' >> $filename
