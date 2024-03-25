import os
import subprocess
import sys

from .utils import get_plugin_dir, printInfoMessage

class DependencyInstaller:
    def __init__(self):
        self.exe = sys.executable.replace('qgis-bin', 'python')

        # TODO ? better dependency handling?
        self.target = get_plugin_dir("dep")
        self.requirements_path = get_plugin_dir("requirements.txt")

        if not os.path.exists(self.target):
            os.makedirs(self.target, exist_ok=True)
        sys.path = [self.target] + sys.path
        
    def install_requirements(self):
        cmd = f"{self.exe} -m pip install -r {self.requirements_path} -t {self.target}"
        subprocess.call(cmd)