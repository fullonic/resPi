"""Application backend logic."""

import sys
import os
import subprocess
import logging
from glob import glob
from logging.handlers import RotatingFileHandler
from functools import wraps
from threading import Thread, Event
from datetime import datetime
from functools import partial  # noqa maybe can be used on save files

try:
    import RPi.GPIO as GPIO

    # ROOT = os.path.join(os.getcwd(), "resPI")
except RuntimeError:
    GPIO = None  # None means that is not running on raspberry pi
    # ROOT = os.getcwd()

from flask_caching import Cache
from flask import (
    Flask,
    render_template,
    redirect,
    url_for,
    request,
    jsonify,
    session,
    flash,
    send_from_directory,
)
from werkzeug.security import generate_password_hash, check_password_hash  # noqa
from flask_socketio import SocketIO

from scripts.utils import (
    to_js_time,
    greeting,
    config_from_file,
    save_config_to_file,
)

ROOT = os.path.dirname(os.path.abspath(__file__))  # app root dir
# App basic configuration
config = {
    "SECRET_KEY": "NONE",
    "CACHE_TYPE": "simple",
    "CACHE_DEFAULT_TIMEOUT": 0,
    "LOGS_FOLDER": f"{ROOT}/logs",
    "LOGS_MB_SIZE": 24578,
    "LOGS_BACKUP": 10,
}  # UNIT: minutes

# DEFINE RASPBERRY PI PINS NUMBERS AND API FUNCTIONS
if GPIO is not None:
    GPIO.setmode(GPIO.BCM)  # Use GPIO Numbers
    PUMP_GPIO = 26  # Digital input to the relay
    GPIO.setup(PUMP_GPIO, GPIO.OUT)  # GPIO Assign mode


# DEFINE APP
# app = Flask(__name__)
if getattr(sys, "frozen", False):
    template_folder = os.path.join(sys._MEIPASS, "templates")
    static_folder = os.path.join(sys._MEIPASS, "static")
    app = Flask(__name__, template_folder=template_folder, static_folder=static_folder)
else:
    app = Flask(__name__)
app.config.from_mapping(config)
_active_threads = {}
exit_thread = Event()
# Setup cache
cache = Cache(app)
cache.set_many((("run_manual", False), ("run_auto", False), ("running", False)))

# SocketIO
socketio = SocketIO(app, async_mode=None)
# thread = None
# thread_lock = Lock()
# Setup logging
logger = app.logger
handler = RotatingFileHandler(
    f"{app.config['LOGS_FOLDER']}/resPI.log",
    maxBytes=app.config["LOGS_MB_SIZE"],
    backupCount=app.config["LOGS_BACKUP"],
)
# handler.setFormatter(logging.Formatter("%(asctime)s - %(name)s - %(message)s"))
handler.setFormatter(logging.Formatter("%(message)s"))
handler.setLevel(logging.WARNING)

app.logger.addHandler(handler)
UNIT = 60  # 1 for seconds, 60 for minutes


def login_required(fn):
    """Decorate to protected against not authenticated users."""
    # Functions warp
    @wraps(fn)
    def wrap(*args, **kwargs):
        if not session.get("auth", False):
            return redirect(url_for("login"))  # Not authenticated
        return fn(*args, **kwargs)

    return wrap


def check_password(password):
    """Check if password is corrected."""
    # Get hash password from os environment to check if matches NOTE: Must be set on pi env
    hash = os.getenv(
        "hash2",
        "pbkdf2:sha256:150000$pMreM10r$6dc02f2deb0725f1f3c70766f44e2aa45d8614556b48e9165740ac6384b4de79",  # noqa
    )
    check = check_password_hash(hash, password)
    if check:
        session["auth"] = True
        return True
    else:
        session["auth"] = False
        return False


####################
# PUMP SETUP AND CONFIGURATION
####################
def switch_on():
    """Turn pump ON."""
    if GPIO:
        GPIO.output(PUMP_GPIO, GPIO.HIGH)  # on
    cache.set("running", True)
    run_mode = "automatic" if cache.get("run_auto") else "manual"  # only for logging
    logger.warning(f"Pump is running | Mode: {run_mode}")


def switch_off():
    """Turn pump OFF."""
    if GPIO:
        GPIO.output(PUMP_GPIO, GPIO.LOW)  # off

    cache.set_many((("cycle_ends_in", None), ("next_cycle_at", None), ("running", False)))
    run_mode = "automatic" if cache.get("run_auto") else "manual"  # only for logging
    logger.warning(f"Pump is off |  Mode: {run_mode}")


# PUMP CYCLE
def pump_cycle(cycle, period):
    """Define how long pump is ON in order to full the fish tank."""
    # Turn on the pump
    started = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    cache.set("total_loops", cache.get("total_loops") + 1)
    switch_on()
    cache.set("cycle_ends_in", to_js_time(cycle, "auto"))
    socketio.emit(
        "automatic_program",
        {
            "data": "Server generated event",
            "running": cache.get("running"),
            "run_auto": cache.get("running"),
            "cycle_ends_in": cache.get("cycle_ends_in"),
            "total_loops": cache.get("total_loops"),
            "auto_run_since": cache.get("auto_run_since"),
        },
        namespace="/resPi",
    )
    # Wait until tank is full
    if not exit_thread.wait(timeout=cycle):  # MINUTES
        if cache.get("run_auto"):  # If still in current automatic program
            # Turn off the pump
            switch_off()
            cache.set("next_cycle_at", to_js_time(period, "auto"))
            socketio.emit(
                "automatic_program",
                {
                    "data": "Server generated event",
                    "running": cache.get("running"),
                    "run_auto": True,
                    "next_cycle_at": cache.get("next_cycle_at"),
                },
                namespace="/resPi",
            )
            ended = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            # Write information to logging file
            # print(
            #     f"""Current program [{cache.get("total_loops")}]: Started {started} | Ended: {ended}"""
            # )
            logger.warning(
                f"""Current program [{cache.get("total_loops")}]: Started {started} | Ended: {ended}"""
            )
        else:  # Ignore previous. Pump is already off
            logger.warning(f"Automatic program: Started {started} was closed forced by user")


####################
# BACKGROUND TASKS
####################
# USER DEFINED PROGRAM
def start_program(app=None):
    """Start a new background thread to run the user program."""
    # program()
    """User defined task.

    Creates a periodic task using user form input.
    """
    # Save starting time programming
    cache.set("auto_run_since", (datetime.now().strftime("%Y-%m-%d %H:%M:%S")))

    user_program = cache.get("user_program")
    # Turn the pump on every x seconds
    period = (user_program.get("close") + user_program.get("wait")) * UNIT
    cycle = user_program.get("flush") * UNIT  # Run the pump for the time of x seconds
    while cache.get("run_auto"):
        pump_cycle(cycle, period)
        if not exit_thread.wait(timeout=period):
            continue
    else:
        return False


####################
# APP ROUTES
####################
@app.route("/", methods=["GET"])
def landing():
    """Endpoint dispatcher to redirect user to the proper route."""
    # Check if user is authenticated
    if not (session.get("auth", False)):
        flash(
            f"{greeting()}, primer cal iniciar la sessió abans d’utilitzar aquesta aplicació",
            "info",
        )
        return redirect(url_for("respi"))
    else:
        flash(f"Hey {greeting()}, benvingut {session['username']}", "info")
        return redirect(url_for("login"))


@app.route("/respi", methods=["GET", "POST"])
@login_required
def respi():
    """Application GUI.

    This route contains all user interface possibilities with the hardware.
    """
    if request.method == "POST":
        # Get information from user form data and run automatic program
        if request.form.get("action", False) == "start":
            # Avoids create a new thread if user reloads browser
            if cache.get("running") or cache.get("run_auto"):
                pass
            else:
                cache.set("run_auto", True)
                flush = int(request.form["flush"])
                wait = int(request.form["wait"])
                close = int(request.form["close"])
                # set program configuration on memory layer
                cache.set("user_program", dict(close=close, flush=flush, wait=wait))
                cache.set("total_loops", 0)
                session["user_program"] = [flush, wait, close]
                # Create a register of the started thread
                global _active_threads
                t = Thread(target=start_program)
                t_name = t.getName()
                _active_threads[t_name] = t  # noqa
                exit_thread.clear()  # set all thread flags to false
                t.start()  # start a fresh new thread with the current program
        elif request.form.get("action", False) == "stop":
            switch_off()  # TODO: Must be checked first
            # Remove counters/timers and stop background thread
            cache.set_many(
                (
                    ("running", False),
                    ("cycle_ends", None),
                    ("next_cycle_at", None),
                    ("run_auto", False),
                )
            )
            exit_thread.set()
        ###########################
        # MANUAL MODE
        ###########################
        if request.form.get("manual", False):
            if request.form["manual"] == "start_manual":
                cache.set_many(
                    (("started_at", to_js_time(run_type="manual")), ("run_manual", True),)
                )
                switch_on()
            else:
                switch_off()
                cache.set("run_manual", False)

    # Populate form inputs with last inserted program or from config file values
    if not cache.get("user_program"):
        config = config_from_file(ROOT)["pump_control_config"]
        flush = int(config["flush"])
        wait = int(config["wait"])
        close = int(config["close"])
    else:
        flush = cache.get("user_program")["flush"]
        wait = cache.get("user_program")["wait"]
        close = cache.get("user_program")["close"]

    return render_template("app.html", flush=flush, wait=wait, close=close)


####################
# EXTRA ROUTES
####################
@app.route("/settings", methods=["POST", "GET"])
def settings():
    config = config_from_file(ROOT)
    if request.method == "POST":
        config = save_config_to_file(request.form.to_dict())
        flash("Configuration updated", "info")
        return redirect("settings")
    return render_template("settings.html", config=config)


####################
# LOGS ROUTES
####################
@app.route("/logs", methods=["GET"])
def logs():
    """Route to see all zip files available to download."""
    logs_folder = glob(f"{app.config['LOGS_FOLDER']}/*.log*")
    # get only the file name and the size of it excluding the path.
    # Create a list of tuples sorted by file name
    logs_folder = sorted([os.path.basename(f) for f in logs_folder])
    logs = [{"id_": i, "name": file_} for i, file_ in enumerate(logs_folder)]
    return render_template("logs.html", logs=logs)


@app.route("/read_log/<log>")
def read_log(log):
    """Open a log file and return it to a html page."""
    file_ = os.path.join(app.config["LOGS_FOLDER"], log)
    with open(file_, "r") as f:
        log_text = [f"<p>{line}</p>" for line in f.readlines()]
        log_ = "\n".join(log_text)
    return log_


@app.route("/download_log/<log>")
def download_log(log):
    """Download a log file."""
    return send_from_directory(app.config["LOGS_FOLDER"], log)


####################
# AUTHENTICATION AND SYSTEM STUFF
####################
@app.route("/login", methods=["GET", "POST"])
def login():
    """User login page."""
    if request.method == "POST":
        password = request.form.get("password", None)
        session["username"] = request.form.get("username", None)
        if check_password(password):
            logger.warning(f"{request.form.get('username')} connectado")
            flash(f"Hey {greeting()}! Benvingut {session['username']}", "info")
            return redirect(url_for("respi"))
        flash("Contrasenya incorrecta", "danger")
    return render_template("login.html")


@app.route("/logout")
def logout():
    """Log out user."""
    session["auth"] = False
    logger.warning(f"{session['username']} left.")
    flash(f"Adeu!! {session['username']}", "info")
    return redirect(url_for("landing"))


@app.route("/turn_off")
def turn_off():
    """Turn off PI."""
    cmd = "sudo shutdown now"
    subprocess.Popen(cmd, shell=True)
    flash(f"Apagar el sistema... Això pot trigar un parell, espereu si us plau", "info")
    return redirect(url_for("landing"))


@app.route("/restart")
def restart():
    """Restart PI."""
    cmd = "sudo reboot"
    subprocess.Popen(cmd, shell=True)
    flash(
        f"""Reinicieu el sistema. Això pot trigar un parell de segons, espereu si us plau.
        Continuar prement F5 fins que torni a actualitzar la pàgina.
        """,
        "info",
    )
    return redirect(url_for("landing"))


@app.route("/status", methods=["GET"])
def get_status():
    """Return information about the different components of the system."""
    return jsonify(
        {
            "running": cache.get("running"),
            "run_auto": cache.get("run_auto"),
            "run_manual": cache.get("run_manual"),
            "cycle_fase": cache.get("cycle_fase"),
            "started_at": cache.get("started_at"),
            "cycle_ends_in": cache.get("cycle_ends_in"),
            "next_cycle_at": cache.get("next_cycle_at"),
            "generating_files": cache.get("generating_files"),
            "total_loops": cache.get("total_loops"),
            "auto_run_since": cache.get("auto_run_since"),
        }
    )


@app.route("/user_time/<local_time>", methods=["GET", "POST"])
def update_time(local_time):
    """Get user local time to update server time."""
    update_time = ["sudo", "date", "-s", "{local_time}"]
    subprocess.rum(update_time)
    return redirect(url_for("login"))


if __name__ == "__main__":
    socketio.run(app, debug=True, host="0.0.0.0")
