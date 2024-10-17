
from qgis.PyQt.QtWidgets import QProgressBar
from qgis.PyQt import QtCore
import riogisoffline.plugin.utils as utils
import traceback
from .syncronizer import Syncronizer
from abc import abstractmethod


class MultiThreadJob:
    """
    Class that handles multi threading so that functions can run in the background

    Attributes:
    riogis : RioGIS
        main RioGIS-object
    
    """

    def __init__(self, riogis):
        self.riogis = riogis

    def startSyncWorker(self):
        """
        Start worker in new thread that runs Syncronizer.sync_now()
        """
        utils.printInfoMessage("Starter synkronisering")
        self.startWorker(SyncWorker)

    def startUploadWorker(self):
        """
        Start worker in new thread that runs AzureBlobStorageConnection.upload_dir()
        """
        utils.printInfoMessage("Starter opplasting")
        self.startWorker(UploadWorker)


    def startWorker(self, worker_class):
        """
        Start a worker of given class in new thread

        Args:
            worker_class (QtCore.QObject): worker class
        """
        
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
        worker.warning.connect(self.workerWarning)

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


    def workerFinished(self, has_failed=False):
    
        self.worker.finished_running(has_failed=has_failed)

        # clean up the worker and thread
        self.worker.deleteLater()
        self.thread.quit()
        self.thread.wait()
        self.thread.deleteLater()

        self.riogis.iface.mainWindow().statusBar().removeWidget(self.bar)
        
        utils.set_busy_cursor(False)

    def workerError(self, e, exception_string):
        utils.printCriticalMessage('Worker thread raised an exception:\n{}'.format(exception_string))

        self.workerFinished(has_failed=True)

    def workerWarning(self, msg):
        utils.printWarningMessage(msg, message_duration=5)


class Worker(QtCore.QObject):
    def __init__(self, riogis):
        QtCore.QObject.__init__(self)
        self.killed = False
        self.riogis = riogis

    def kill(self):
        self.killed = True

    @abstractmethod
    def run(self):
        pass

    @abstractmethod
    def finished_running(self, has_failed):
        pass

    # emit has_failed (bool) when finished
    finished = QtCore.pyqtSignal(bool)
    
    error = QtCore.pyqtSignal(Exception, str)
    warning = QtCore.pyqtSignal(str)
    info = QtCore.pyqtSignal(str)

    progress = QtCore.pyqtSignal(int)
    process_name = QtCore.pyqtSignal(str)

class SyncWorker(Worker):

    def run(self):
        try:

            # disable button when running
            self.riogis.dlg.btnSync.setEnabled(False)

            sync = Syncronizer(self, self.riogis.azure_connection)
            sync.sync_now()
        except Exception as e:
            # forward the exception upstream
            self.error.emit(e, traceback.format_exc())

    def finished_running(self, has_failed):
        if has_failed:
            utils.printWarningMessage("Noe gikk galt! Synkronisering avbrutt.")
            return

        self.riogis.refresh_map()
        utils.printInfoMessage("Ferdig synkronisert", message_duration=1)

        # enable button when finished
        self.riogis.dlg.btnSync.setEnabled(True)

class UploadWorker(Worker):

    def run(self):
        try:

            # disable button when running
            self.riogis.dlg.btnUpload.setEnabled(False)

            dir_path = self.riogis.dlg.selectUploadDir.filePath()
            self.riogis.azure_connection.upload_dir(dir_path, self)
        except Exception as e:
            # forward the exception upstream
            self.error.emit(e, traceback.format_exc())

    def finished_running(self, has_failed):
        if has_failed:
            utils.printWarningMessage("Noe gikk galt! Opplasting avbrutt.")
            return
        
        utils.printInfoMessage("Opplasting gjennomført", message_duration=1)

        # enable button when finished
        self.riogis.dlg.btnUpload.setEnabled(True)
