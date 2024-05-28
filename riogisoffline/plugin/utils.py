import os
import json

from qgis.utils import iface
from qgis.core import Qgis
from qgis.PyQt import QtGui, QtWidgets, QtCore

default_message_duration = 3

def get_plugin_dir(path_to_join=None):

    plugin_dir = os.getenv('PLUGIN_DIR')

    if not plugin_dir:
        # get parent of current dir if PLUGIN_DIR is not set
        plugin_dir = os.path.dirname(os.path.dirname(__file__))

    if not path_to_join:
        return plugin_dir

    return os.path.join(plugin_dir, path_to_join)

def load_json(path):

        if os.path.exists(path):
            with open(path) as f:
                return json.load(f)
        else:
            raise Exception(f"Missing settings: No file named {path}")

def printInfoMessage(message, message_duration=default_message_duration):
    """Print info message in Qgis interface

    Args:
        message (String): message to printInfoMessage
    """

    iface.messageBar().pushMessage(
            "", message, level=Qgis.Info, duration=message_duration
       )
    
def printWarningMessage(message, message_duration=default_message_duration):
    """Print warning message in Qgis interface

    Args:
        message (String): message to printInfoMessage
    """

    iface.messageBar().pushMessage(
            "", message, level=Qgis.Warning, duration=message_duration
       )
    
def printCriticalMessage(message, message_duration=default_message_duration):
    """Print critical message in Qgis interface

    Args:
        message (String): message to printInfoMessage
    """

    iface.messageBar().pushMessage(
            "", message, level=Qgis.Critical, duration=message_duration
       )
    
def printSuccessMessage(message, message_duration=default_message_duration):
    """Print success message in Qgis interface

    Args:
        message (String): message to printInfoMessage
    """

    iface.messageBar().pushMessage(
            "", message, level=Qgis.Success, duration=message_duration
       )

def get_user_settings_path():
    # bruker_settings.json is placed in python-dir of qgis default profile
    return get_plugin_dir("../../../bruker_settings.json")

def get_settings_path():
    return get_plugin_dir("settings.json")

def get_db_name():
    return "oslo_offline.db"

def set_busy_cursor(set_busy=True):
    """Set cursor to BusyCursor (or back to ArrowCursor)

    Args:
        set_busy (bool, optional): Sets BusyCursor if True, and ArrowCursor if False. Defaults to True.
    """
    if set_busy:
        QtWidgets.QApplication.setOverrideCursor(QtGui.QCursor(QtCore.Qt.BusyCursor))
    else:
        QtWidgets.QApplication.restoreOverrideCursor()
