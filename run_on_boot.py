"""Start a new subprocess on system boot.

Also can be used to start the system on background using a ssh connection.

This script will be called using the rc.local file.

Edit the file:
sudo nano /etc/rc.local

Add startup script to the rc.local. Must be the full path:

# SENSOR APP STARTUP SCRIPT
python3 /home/pi/resPI/run_on_boot.py

"""

import subprocess
import os

# cmd = "python3 /home/somnium/Desktop/Projects/resPI/app.py".split()
cmd = ["pwd", "ls"]
subprocess.run(cmd)
