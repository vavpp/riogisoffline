import os
import subprocess
import sys

import riogisoffline.plugin.utils as utils

class DependencyInstaller:
    def __init__(self):
        self.exe = os.path.join(os.path.dirname(sys.executable), "python.exe")
        self.requirements_path = utils.get_plugin_dir("requirements.txt")
        
    def install_requirements(self):
        cmd = f"{self.exe} -m pip install -r {self.requirements_path} --user"
        subprocess.call(cmd)
