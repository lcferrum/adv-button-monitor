#!/usr/bin/python
#N9 Button Monitor
#Copyright 2012 Elliot Wolk
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.

from QmSystem import QmKeys
from PySide.QtGui import QApplication, QWidget
from PySide.QtCore import QBasicTimer
from QtMobility.MultimediaKit import QCamera, QCameraExposure
from QtMobility.SystemInfo import QSystemDeviceInfo

import sys
import os
import re
import time
import subprocess

STATE_ON = 2
STATE_OFF = 0

BUTTON_VOLUME_UP = 2
BUTTON_VOLUME_DOWN = 3
BUTTON_POWER = 20

MUSIC_SUITE_STATE_PLAYING = 1
MUSIC_SUITE_STATE_PAUSED = 2
MUSIC_SUITE_STATE_OFF = 0
###############

#montonic timer so that ntp adjustments cant throw off double-click timing..
import ctypes
__all__ = ["monotonic_time"]
CLOCK_MONOTONIC = 1 # see <linux/time.h>
CLOCK_MONOTONIC_RAW = 4 # see <linux/time.h>
class timespec(ctypes.Structure):
    _fields_ = [
        ('tv_sec', ctypes.c_long),
        ('tv_nsec', ctypes.c_long)
    ]
librt = ctypes.CDLL('librt.so.1', use_errno=True)
clock_gettime = librt.clock_gettime
clock_gettime.argtypes = [ctypes.c_int, ctypes.POINTER(timespec)]

def monotonic_time():
  t = timespec()
  if clock_gettime(CLOCK_MONOTONIC_RAW, ctypes.pointer(t)) != 0:
    errno_ = ctypes.get_errno()
    raise OSError(errno_, os.strerror(errno_))
  return t.tv_sec + t.tv_nsec * 1e-9

###############
configFilePath = "/home/user/.config/n9-button-monitor.ini"
deprecatedConfigFilePath = "/home/user/.config/n9-button-monitor.conf"

class Config():
  def __init__(self):
    self.actions = []
    self.torchAutoShutOffTimeMs=300000
    self.longClickDelayMs=400
    self.doubleClickDelayMs=400
    self.trebleClickDelayMs=600
  def getDefaultConfig(self):
    return (""
      + "#DEFAULT CONFIG\n"
      + "torchAutoShutOffTimeMs=30000\n"
      + "longClickDelayMs=400\n"
      + "doubleClickDelayMs=400\n"
      + "trebleClickDelayMs=600\n"
      + "action=torchOn,volumeUp,longClickStart,screenLocked\n"
      + "action=torchOff,volumeUp,longClickStop,screenLocked\n"
      + "action=cameraFocus,volumeUp,longClickStart,cameraAppFocused\n"
      + "action=cameraSnap,volumeUp,longClickStop,cameraAppFocused\n"
      + "action=cameraSnap,volumeUp,singleClick,cameraAppFocused\n"
      )
  def getIntFieldRegex(self, fieldName):
    return re.compile("^" + fieldName + "=" + "(\d+)" + "$")
  def getActionRegex(self):
    ptrn = (""
           + "^"
           + "\\s*action\\s*=\\s*"
           + "(?P<actionName>" + "|".join(actions.keys()) + ")"
           + "(?:" + "\(" + "(?P<actionParam>[^)]*)" + "\)" + ")?"
           + "\\s*,\\s*"
           + "(?P<button>" + "|".join(buttons.keys()) + ")"
           + "\\s*,\\s*"
           + "(?P<clickType>" + "|".join(clickTypes) + ")"
           + "\\s*,\\s*"
           + "(?P<condName>" + "|".join(conds.keys()) + ")"
           + "(?:" + "\(" + "(?P<condParam>[^)]*)" + "\)" + ")?"
           + "\\s*(#.*)?"
           + "$"
           )
    return re.compile(ptrn)
  def parse(self):
    if os.path.isfile(configFilePath):
      config = open(configFilePath,"rb").read()
    elif os.path.isfile(deprecatedConfigFilePath):
      config = open(deprecatedConfigFilePath,"rb").read()
      print ("WARNING: config file should be '" + configFilePath + "'\n" +
             "{not '" + deprecatedConfigFilePath + "'}")
    else:
      config = self.getDefaultConfig()
      print "WARNING: no config file at '" + configFilePath + "'"
      print "Using default config:\n" + config

    actionRe = self.getActionRegex()
    integerRe = re.compile(
      "^\\s*(?P<key>[a-zA-Z0-9]+)" + "\\s*=\\s*" + "(?P<value>\d+)\\s*(#.*)?$")
    commentRe = re.compile("^\\s*#.*$")
    emptyRe = re.compile("^\\s*$")
    for line in config.splitlines():
      actionMatch = actionRe.match(line)
      integerMatch = integerRe.match(line)
      commentMatch = commentRe.match(line)
      emptyMatch = emptyRe.match(line)
      key = None
      if integerMatch != None:
        key = integerMatch.group("key")
        val = int(integerMatch.group("value"))

      if commentMatch != None or emptyMatch != None:
        pass
      elif actionMatch != None:
        self.actions.append(Action(
          actionName = actionMatch.group("actionName"),
          actionParam = actionMatch.group("actionParam"),
          button = actionMatch.group("button"),
          clickType = actionMatch.group("clickType"),
          condName = actionMatch.group("condName"),
          condParam = actionMatch.group("condParam")
        ))
      elif key == "torchAutoShutOffTimeMs":
        self.torchAutoShutOffTimeMs = val
      elif key == "longClickDelayMs":
        self.longClickDelayMs = val
      elif key == "doubleClickDelayMs":
        self.doubleClickDelayMs = val
      elif key == "trebleClickDelayMs":
        self.trebleClickDelayMs = val
      else:
        print >> sys.stderr, "Unparseable config entry: " + line
        sys.exit(1)

###############

def getConds():
  return { "screenLocked": lambda: QSystemDeviceInfo().isDeviceLocked()
         , "cameraAppFocused": lambda: isAppOnTop("camera-ui")
         , "appFocused": lambda x: lambda: isAppOnTop(x)
         }

def isAppOnTop(app):
  winId = readProc(["xprop", "-root", "_NET_ACTIVE_WINDOW"]) [40:]
  winCmd = readProc(["xprop", "-id", winId, "WM_COMMAND"]) [24:-4]
  return app in winCmd

###############

def getActions():
  return { "cameraSnap": lambda: drag("820x240,820x240")
         , "cameraFocus": lambda: drag("820x240-820x100*200+5")
         , "torchOn": lambda: torch.on()
         , "torchOff": lambda: torch.off()
         , "torchToggle": lambda: torch.toggle()
         , "cmd": lambda x: lambda: shellCmd(x)
         , "drag": lambda x: lambda: drag
         , "musicPlayPause": lambda: musicPlayPause()
         , "musicNext": lambda: musicSuiteDbus("next")
         , "musicPrev": lambda: musicSuiteDbus("previous")
         }

def musicPlayPause():
  state = musicSuiteDbus("playbackState")
  try:
    state = int(state.strip())
  except e:
    print >> sys.stderr, "ERROR READING MUSIC SUITE STATE: " + str(e)

  if state == MUSIC_SUITE_STATE_PLAYING:
    musicSuiteDbus("pausePlayback")
  elif state == MUSIC_SUITE_STATE_PAUSED:
    musicSuiteDbus("resumePlayback")

def musicSuiteDbus(methodShortName):
  servicename = "com.nokia.maemo.meegotouch.MusicSuiteService"
  path = "/"
  method = "com.nokia.maemo.meegotouch.MusicSuiteInterface." + methodShortName
  return readProc(["qdbus", servicename, path, method])

def drag(arg):
  runcmd(["xresponse", "-w", "1", "-d", arg])

###############

def shellCmd(cmd):
  runcmd(['sh', '-c', cmd])

def runcmd(cmdArr):
  print 'running cmd: "' + ' '.join(cmdArr) + '"'
  subprocess.Popen(cmdArr)

def readProc(cmdArr):
  print 'running cmd: "' + ' '.join(cmdArr) + '"'
  out, err = subprocess.Popen(cmdArr, stdout=subprocess.PIPE).communicate()
  return out

###############

class TorchAutoShutOff(QWidget):
  def __init__(self, torch):
    super(TorchAutoShutOff, self).__init__()
    self.torch = torch
    self.timer = QBasicTimer()
  def schedule(self, time):
    self.timer.start(time, self)
  def cancel(self):
    self.timer.stop()
  def timerEvent(self, e):
    self.timer.stop()
    if self.torch.state == "on":
      print "auto shut-off"
      self.torch.off()

class Torch():
  def __init__(self):
    self.state = "off"

  def initCamera(self):
    self.camera = QCamera()
    self.autoShutOff = TorchAutoShutOff(self)
    self.on()
    self.autoShutOff.schedule(500)

  def toggle(self):
    if self.state == "on":
      self.off()
    else:
      self.on()

  def on(self):
    print "torch on"
    self.camera.setCaptureMode(QCamera.CaptureVideo)
    self.camera.exposure().setFlashMode(QCameraExposure.FlashTorch)
    self.camera.start()
    self.state = "on"
    self.autoShutOff.schedule(config.torchAutoShutOffTimeMs)

  def off(self):
    self.autoShutOff.cancel()
    print "torch off"
    self.camera.setCaptureMode(QCamera.CaptureStillImage)
    self.camera.exposure().setFlashMode(QCameraExposure.FlashManual)
    self.camera.unlock()
    self.camera.unload()
    self.state = "off"

###############

clickTypes = ["singleClick","doubleClick","trebleClick",
              "longClickStart","longClickStop"]

buttons = { "volumeUp": BUTTON_VOLUME_UP
          , "volumeDown": BUTTON_VOLUME_DOWN}

class Action():
  def __init__(self, actionName, actionParam,
               button, clickType, condName, condParam):
    self.key = buttons[button]
    self.clickType = clickType
    self.actionName = actionName
    self.actionParam = actionParam
    self.actionLambda = self.getLambda(actions, actionName, actionParam)
    self.condName = condName
    self.condParam = condParam
    self.condLambda = self.getLambda(conds, condName, condParam)
  def __str__(self):
    if self.actionParam == None:
      param = ""
    else:
      param = "(" + self.actionParam + ")"
    action = self.actionName + param
    return (str(self.key) + "[" + self.clickType + "]: " + action)
  def getLambda(self, lambdaDict, lambdaName, lambdaParam):
    lam = lambdaDict[lambdaName]
    assert self.isLambda(lam), "'" + lambdaName + "' not defined"
    if lambdaParam != None:
      try:
        lam = lam(lambdaParam)
        assert self.isLambda(lam)
      except:
        print >> sys.stderr, (
          "'" + lambdaName + "' does not accept an argument\n" +
          "{given: '" + lambdaParam + "'}")
        sys.exit(1)
    return lam
  def isLambda(self, v):
    return isinstance(v, type(lambda: None)) and v.__name__ == '<lambda>'


torch = Torch()
actions = getActions()
conds = getConds()
config = Config()
config.parse()

class ClickTimer(QWidget):
  def __init__(self, key):
    super(ClickTimer, self).__init__()
    self.timer = QBasicTimer()
    self.key = key
    self.presses = []
    self.releases = []
    self.keyPressed = False
    self.longClickStarted = False
    keyActions = filter(lambda a: a.key == self.key, config.actions)
    self.actionsByClickType = dict()
    for clickType in clickTypes:
      acts = filter(lambda a: a.clickType == clickType, keyActions)
      self.actionsByClickType[clickType] = acts
  def nowMs(self):
    return monotonic_time() * 1000
  def receivePress(self):
    self.presses.append(self.nowMs())
    self.checkEvent()
  def receiveRelease(self):
    self.releases.append(self.nowMs())
    self.checkEvent()
  def checkEvent(self):
    now = self.nowMs()
    self.timer.stop()
    if len(self.presses) == 0:
      self.reset()
      return
    elif len(self.presses) == 1:
      press = self.presses[0]
      if len(self.releases) == 0:
        if now - press > config.longClickDelayMs:
          self.longClickStarted = True
          self.longClickStart()
        else:
          self.schedule(config.longClickDelayMs - (now - press))
          return
      elif len(self.releases) == 1:
        if self.longClickStarted:
          self.longClickStop()
        elif now - press > config.doubleClickDelayMs:
          self.singleClick()
        else:
          self.schedule(config.doubleClickDelayMs - (now - press))
      else:
        self.singleClick()
    elif len(self.presses) == 2:
      press = self.presses[0]
      if now - press > config.trebleClickDelayMs:
        self.doubleClick()
      else:
        self.schedule(config.trebleClickDelayMs - (now - press))
    elif len(self.presses) >= 3:
      self.trebleClick()
    self.releases
  def schedule(self, time):
    self.timer.start(time, self)
  def reset(self):
    self.timer.stop()
    self.presses = []
    self.releases = []
    self.longClickStarted = False
  def singleClick(self):
    self.reset()
    print str(self.key) + ": single"
    self.performActions("singleClick")
  def doubleClick(self):
    self.reset()
    print str(self.key) + ": double"
    self.performActions("doubleClick")
  def trebleClick(self):
    self.reset()
    print str(self.key) + ": treble"
    self.performActions("trebleClick")
  def longClickStart(self):
    print str(self.key) + ": long-start"
    self.performActions("longClickStart")
  def longClickStop(self):
    self.reset()
    print str(self.key) + ": long-stop"
    self.performActions("longClickStop")
  def performActions(self, clickType):
    for a in self.actionsByClickType[clickType]:
      if a.condLambda == None or a.condLambda():
        a.actionLambda()
  def timerEvent(self, e):
    self.timer.stop()
    self.checkEvent()
  def keyEvent(self, state):
    if state == STATE_ON and not self.keyPressed:
      self.keyPressed = True
      self.receivePress()
    elif state == STATE_OFF:
      self.keyPressed = False
      self.receiveRelease()

def main():
  app = QApplication(sys.argv)
  torch.initCamera()
  keys = QmKeys()
  buttonTimers = dict()
  for b in buttons.values():
    buttonTimers[b] = ClickTimer(b)
  keys.keyEvent.connect(lambda k, s:
    (k in buttonTimers and buttonTimers[k].keyEvent(s)))
  app.exec_()

if __name__ == "__main__":
  sys.exit(main())

