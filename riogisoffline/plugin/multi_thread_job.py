
from qgis.PyQt.QtWidgets import QProgressBar
from qgis.PyQt import QtCore
import riogisoffline.plugin.utils as utils
import traceback
from .syncronizer import Syncronizer

class MultiThreadJob:

    def __init__(self, riogis):
        self.riogis = riogis

    def startSyncWorker(self):
        utils.printInfoMessage("Starter synkronisering")
        self.startWorker(SyncWorker)

    def startUploadWorker(self):
        utils.printInfoMessage("Starter opplasting")
        self.startWorker(UploadWorker)


    def startWorker(self, worker_class):
        
        if not self.riogis.establish_azure_connection():
            return
        
        utils.set_busy_cursor(True)

        # create a new worker instance
        worker = worker_class(self.riogis)

        # start the worker in a new thread
        thread = QtCore.QThread(self.riogis.dlg)
        worker.moveToThread(thread)

        worker.finished.connect(self.workerFinished)
        worker.error.connect(self.workerError)

        self.bar = QProgressBar()
        self.bar.setRange(0, 100)
        self.riogis.iface.mainWindow().statusBar().addWidget(self.bar, stretch=2)
        
        worker.progress.connect(
            lambda p: self.bar.setValue(p)
        )

        def set_new_process(text):
            self.bar.setValue(0)
            self.bar.setFormat(f"{text} - %p%")

        worker.process_name.connect(set_new_process)

        worker.info.connect(lambda msg: utils.printInfoMessage(msg, message_duration=1))


        thread.started.connect(worker.run)
        thread.start()

        self.thread = thread
        self.worker = worker

        # disable buttons when running
        self.riogis.dlg.btnSync.setEnabled(False)
        self.riogis.dlg.btnUpload.setEnabled(False)



    def workerFinished(self):
        # clean up the worker and thread
        self.worker.deleteLater()
        self.thread.quit()
        self.thread.wait()
        self.thread.deleteLater()

        # enable buttons when finished
        self.riogis.dlg.btnSync.setEnabled(True)
        self.riogis.dlg.btnUpload.setEnabled(True)

        self.riogis.iface.mainWindow().statusBar().removeWidget(self.bar)
        
        utils.set_busy_cursor(False)
        
        utils.printInfoMessage("Jobb gjennomført", message_duration=1)

    def workerError(self, e, exception_string):
        utils.printCriticalMessage('Worker thread raised an exception:\n{}'.format(exception_string))

        self.workerFinished()

    def workerWarning(self, msg):
        utils.printWarningMessage(msg)


class SyncWorker(QtCore.QObject):
    def __init__(self, riogis):
        QtCore.QObject.__init__(self)
        self.killed = False
        self.riogis = riogis

    def run(self):
        try:
            sync = Syncronizer(self, self.riogis.azure_connection)
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

class UploadWorker(QtCore.QObject):
    def __init__(self, riogis):
        QtCore.QObject.__init__(self)
        self.killed = False
        self.riogis = riogis

    def run(self):
        try:
            dir_path = self.riogis.dlg.selectUploadDir.filePath()
            self.riogis.azure_connection.upload_dir(dir_path, self)
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
    # TODO lag en worker wrapper class som disse kan extende