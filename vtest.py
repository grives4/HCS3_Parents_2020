import os
import sys
import logging
from pandora import clientbuilder
import re
import time
import threading
import xml.etree.ElementTree as ET
import pdb
import subprocess
import time
import fcntl
import select
import socket
from shutil import which
from queue import Queue


logger = logging.getLogger('HCS3')

class SilentPopen(subprocess.Popen):
    """A Popen varient that dumps it's output and error
    """

    def __init__(self, *args, **kwargs):
        self._dev_null = open(os.devnull, "w")
        kwargs["stdin"] = subprocess.PIPE
        kwargs["stdout"] = subprocess.PIPE
        kwargs["stderr"] = self._dev_null
        super().__init__(*args, **kwargs)

    def __del__(self):
        self._dev_null.close()
        super().__del__()

CHUNK_SIZE = 1024

_cmd = [which("vlc"),"-I", "rc", "--advanced", "--rc-fake-tty", "-q"]
_process = SilentPopen(_cmd)
flags = fcntl.fcntl(_process.stdout, fcntl.F_GETFL)
fcntl.fcntl(_process.stdout, fcntl.F_SETFL, flags | os.O_NONBLOCK)
_process.stdin.write("{}\n".format('add test').encode("utf-8"))
_process.stdin.flush()
readers, _, _ = select.select([_process.stdout], [], [], 1)
for handle in readers:
    value = handle.read(CHUNK_SIZE).strip()
    print(value)
time.sleep(4)
_process.stdin.write("{}\n".format('status').encode("utf-8"))
_process.stdin.flush()
time.sleep(4)
readers, _, _ = select.select([_process.stdout], [], [], 1)
for handle in readers:
    value = handle.read(CHUNK_SIZE).strip()
    print(value)
_process.kill()

        