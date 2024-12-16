import os
import json
import requests
import csv
import pandas as pd

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

def write_changed_status_to_file(settings, lsid, new_status, comment, project_area_id):
        try:
            user_settings = get_user_settings_path()
            # read user settings
            user_settings = load_json(user_settings)
            file_folder_path = user_settings["file_folder"]
            
            changed_status_filename = os.path.join(file_folder_path, settings["changed_status_filename"])

            status_change_dict = {
                "lsid": [lsid],
                "new_status": [new_status],
                "comment": [comment],
                "project_area_id": [project_area_id]
            }

            status_df = pd.DataFrame.from_dict(status_change_dict)

            # don't write header if file exists
            if os.path.exists(changed_status_filename):
                status_df.to_csv(changed_status_filename, mode="a", header=False, index=False) 
            else:
                field_headers = status_change_dict.keys()
                status_df.to_csv(changed_status_filename, mode="a", header=field_headers, index=False) 

        except Exception as e:
            printWarningMessage(str(e))
            return False

        return True

def change_project_status(settings, layer, project_feature, new_status, comment):
        project_area_id = project_feature["project_area_id"]

        # write to file
        write_changed_project_status_to_file(settings, project_area_id, new_status, comment)

        # repaint project
        layer.startEditing()

        project_feature["status"] = new_status
        layer.updateFeature(project_feature)

        layer.commitChanges()
        layer.triggerRepaint()

def write_changed_project_status_to_file(settings, project_area_id, new_status, comment):
        try:
            user_settings = get_user_settings_path()
            # read user settings
            user_settings = load_json(user_settings)
            file_folder_path = user_settings["file_folder"]
            
            changed_project_status_filename = os.path.join(file_folder_path, settings["changed_project_status_filename"])

            status_change_dict = {
                "GlobalID": [project_area_id],
                "new_status": [new_status],
                "comments_inspector": [comment]
            }

            status_df = pd.DataFrame.from_dict(status_change_dict)

            # don't write header if file exists
            if os.path.exists(changed_project_status_filename):
                status_df.to_csv(changed_project_status_filename, mode="a", header=False, index=False) 
            else:
                field_headers = status_change_dict.keys()
                status_df.to_csv(changed_project_status_filename, mode="a", header=field_headers, index=False) 

        except Exception as e:
            printWarningMessage(str(e))
            return False

        return True

def get_status_text(status, status_items):
    status_values = status_items["values"]
    status_keys = status_items["keys"]

    if not status in status_values:
        return "Ukjent"

    status_text = status_keys[status_values.index(status)]

    return status_text