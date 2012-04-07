echo; echo INSTALLING DEPENDENCIES
apt-get install \
  xresponse \
  x11-utils \
  python-qmsystem \
  python-qtmobility.multimediakit \
  python-qtmobility.systeminfo \
  python-pyside.qtgui \
  python-pyside.qtcore \
;

INSTALL_DIR=/opt/n9-button-monitor
UPSTART_DIR=/etc/init
CONF_DIR=/home/user/.config

echo; echo COPYING EXEC TO $INSTALL_DIR
mkdir -p $INSTALL_DIR
cp start.sh $INSTALL_DIR
cp n9-button-monitor.py $INSTALL_DIR
chmod +x $INSTALL_DIR/n9-button-monitor.py

echo; echo COPYING UPSTART SCRIPT TO $UPSTART_DIR
cp n9-button-monitor.conf $UPSTART_DIR

if [ -e $CONF_DIR/n9-button-monitor.ini ]; then
  echo; echo LEAVING EXISTING INI
elif [ -e $CONF_DIR/n9-button-monitor.conf ]; then
  echo; echo RENAMING n9-button-monitor.conf to n9-button-monitor.ini
  mv $CONF_DIR/n9-button-monitor.conf $CONF_DIR/n9-button-monitor.ini
else
  echo; echo INSTALLING DEFAULT INI
  cp n9-button-monitor.ini $CONF_DIR
fi
