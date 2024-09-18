# import some modules used in the example
from qgis.core import *
from qgis.PyQt import QtCore
import traceback
from .syncronizer import Syncronizer

class Worker(QtCore.QObject):
    def __init__(self, azure_connection):
        QtCore.QObject.__init__(self)
        self.killed = False
        self.azure_connection = azure_connection

    def run(self):
        try:
            sync = Syncronizer(self, self.azure_connection)
            sync.sync_now()
        except Exception as e:
            # forward the exception upstream
            self.error.emit(e, traceback.format_exc())

    def kill(self):
        self.killed = True

    finished = QtCore.pyqtSignal()
    error = QtCore.pyqtSignal(Exception, str)
    warning = QtCore.pyqtSignal(str)
    info = QtCore.pyqtSignal(str)

    progress = QtCore.pyqtSignal(int)
    process_name = QtCore.pyqtSignal(str)

