import subprocess
import os
from time import sleep
import json
os.getcwd()

app_folder = os.getcwd()
cfg = {"app_folder": app_folder}

os.chdir(app_folder)

cmd = "python -m venv venv".split()

print("-" * 20)
print("Setting up venv")
subprocess.Popen(cmd, shell=True, stdout=subprocess.PIPE)
print("-" * 20)
print("Activating venv")
print("-" * 20)
active_venv = os.path.join(app_folder, f"venv{os.sep}Scripts{os.sep}activate")

py = os.path.join(app_folder, f"venv{os.sep}Scripts{os.sep}python.exe")
pip = os.path.join(app_folder, f"venv{os.sep}Scripts{os.sep}pip.exe")
cfg["venv_python"] = py
cfg["venv_pip"] = pip
print("\n")
print("-" * 20)
print("Setting up all things for you ", end="")
print("-" * 20)
while not (os.path.exists(py) and os.path.exists(pip)):
    print("#", end="", flush=True)
    sleep(0.5)

else:
    print("\n")
    flask_ = [py, "-m", "pip", "install", "-r", "requirements.txt"]
    subprocess.run(flask_, shell=True, stdout=subprocess.PIPE)
    print("INSTALLED flask")
    sleep(2)


with open("WIN/config.json", "w") as cfg_file:
    json.dump(cfg, cfg_file)
