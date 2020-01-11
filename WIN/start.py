import subprocess
import os
import sys
from threading import Thread
from time import sleep

app_folder = 'C:\\Users\\somnium\\Desktop\\resPi\\server.py'
pyw = "C:\\Users\\somnium\\Desktop\\resPi\\venv\Scripts\\python.exe"
server = [pyw, app_folder]

subprocess.call(server)
