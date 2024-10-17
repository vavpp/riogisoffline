import os
import json
import requests

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

    if not iface:
        return

    iface.messageBar().pushMessage(
            "", message, level=Qgis.Info, duration=message_duration
       )
    
def printWarningMessage(message, message_duration=default_message_duration):
    """Print warning message in Qgis interface

    Args:
        message (String): message to printInfoMessage
    """

    if not iface:
        return

    iface.messageBar().pushMessage(
            "", message, level=Qgis.Warning, duration=message_duration
       )
    
def printCriticalMessage(message, message_duration=default_message_duration):
    """Print critical message in Qgis interface

    Args:
        message (String): message to printInfoMessage
    """

    if not iface:
        return

    iface.messageBar().pushMessage(
            "", message, level=Qgis.Critical, duration=message_duration
       )
    
def printSuccessMessage(message, message_duration=default_message_duration):
    """Print success message in Qgis interface

    Args:
        message (String): message to printInfoMessage
    """

    if not iface:
        return

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

def fcode_to_text(fcode):
    """
    Convert fcode to fcode text

    Args:
        fcode (str): fcode

    Returns:
        str: fcode text
    """
    
    fcode_text_map = {
        'AF': 'Avløp',
        'OV': 'Overvann',
        'VL': 'Vann',
        'SP': 'Spillvann',
    }
    
    if not fcode in fcode_text_map:
        return 'Ukjent'
    
    return fcode_text_map[fcode]

def has_internet_connection():
    """
    Check if user has internet connection

    Returns:
        bool: is connected to internet
    """
    try:
        requests.get("https://www.oslo.kommune.no", timeout=5)
        return True
    except requests.ConnectionError:
        return False  

def synced_files_exist():
    """
    Checks if DB- and backgound map-files exist

    Returns:
        bool: Files exist
    """

    filenames = [
        os.getenv('BACKGROUND_MAP'),
        os.getenv('SOURCE_MAP')
    ]

    for filename in filenames:
        if not os.path.exists(filename):
            return False 

    return True