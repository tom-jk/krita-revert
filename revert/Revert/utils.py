from PyQt5.QtCore import Qt
from functools import reduce
from krita import *
app = Krita.instance()

setting_defaults = {"custom_icons_theme":"follow"}

def readSetting(setting, default_override=None):
    return app.readSetting("TomJK_Revert", setting, default_override if default_override!=None else setting_defaults[setting])

def writeSetting(setting, value):
    app.writeSetting("TomJK_Revert", setting, value)

def bool2str(boolval):
    return "true" if boolval else "false"

def str2bool(strval):
    return True if strval == "true" else False

def str2qtcheckstate(strval, true="true"):
    return Qt.Checked if strval == true else Qt.Unchecked

def bool2flag(*args):
    return reduce(lambda a,b: a+b, (("1" if b else "0") for b in args))

def flag2bool(strval):
    return True if strval == "1" else False
