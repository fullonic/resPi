"""Application backend logic."""

import sys
import os
import subprocess
import logging
from glob import glob
from logging.handlers import RotatingFileHandler
from threading import Thread, Event
from datetime import datetime
from functools import partial  # noqa maybe can be used on save files
from pathlib import Path

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
    _set_time,
    login_required,
    check_password,
)

# ROOT = os.path.dirname(os.path.abspath(__file__))  # app root dir
ROOT = Path(__file__).parent  # app root dir
print(f"{ROOT=}")
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

# Setup logging
logger = app.logger
handler = RotatingFileHandler(
    f"{app.config['LOGS_FOLDER']}/resPI.log",
    maxBytes=app.config["LOGS_MB_SIZE"],
    backupCount=app.config["LOGS_BACKUP"],
)
# handler.setFormatter(logging.Formatter("%(asctime)s - %(name)s - %(message)s"))
handler.setFormatter(logging.Formatter("%(asctime)s || %(message)s"))
handler.setLevel(logging.WARNING)

app.logger.addHandler(handler)
UNIT = 1  # 1 for seconds, 60 for minutes


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
    _set_time(cache.get("user_time"))

    # Save starting time programming
    cache.set("auto_run_since", (datetime.now().strftime("%d-%m-%Y %H:%M:%S")))
    user_program = cache.get("user_program")
    wait = user_program.get("wait") * UNIT
    close = user_program.get("close") * UNIT

    # Turn the pump on every x seconds
    period = (user_program.get("close") + user_program.get("wait")) * UNIT
    cycle = user_program.get("flush") * UNIT  # Run the pump for the time of x seconds
    while cache.get("run_auto"):
        pump_cycle(cycle, period)
        # Send message about wait status
        cache.set("cycle_fase", "wait")
        cache.set("cycle_ends_in", to_js_time(wait))
        socketio.emit(
            "automatic_program",
            {
                "data": "Server generated event",
                "running": cache.get("running"),
                "cycle_fase": cache.get("cycle_fase"),
                "run_auto": True,
                "cycle_ends_in": cache.get("cycle_ends_in"),
            },
            namespace="/resPi",
        )
        if not exit_thread.wait(timeout=(user_program.get("wait") * UNIT)):
            # Send message about close status
            cache.set("cycle_fase", "close")
            cache.set("cycle_ends_in", to_js_time(close))
            socketio.emit(
                "automatic_program",
                {
                    "data": "Server generated event",
                    "running": cache.get("running"),
                    "cycle_fase": cache.get("cycle_fase"),
                    "run_auto": True,
                    "cycle_ends_in": cache.get("cycle_ends_in"),
                },
                namespace="/resPi",
            )
            if not exit_thread.wait(timeout=(user_program.get("close") * UNIT)):
                continue
    else:
        return False


#####################
# Active SAFE FISH mode
#####################
def _safe_fish_flag(flag):
    """It sets pump_was_running flag to True or False.

    When experiment starts flag will be True. If user stop the experiment or turn off the
    board using the "turn_off" or "restart" flag will be False.
    In both cases, at the next system boot pump will be off by default.
    However, if there is a power failure during an experiment, at the next startup (when power
    returns), flag will be on True and will start a new cycle using the last experiment
    configuration.
    This is made to avoid fish death because lack of oxygen, related with grid power failure.
    """
    safe_cfg = config_from_file(ROOT)["pump_control_config"]
    safe_cfg["pump_was_running"] = flag
    save_config_to_file(safe_cfg)


safe_cfg = config_from_file(ROOT)["pump_control_config"]
if safe_cfg["safe_fish"] and safe_cfg.get("pump_was_running", False):
    # Active last user experiment
    # Write to log that failure happen
    cache.set("run_auto", True)
    cache.set(
        "user_program",
        dict(close=safe_cfg["close"], flush=safe_cfg["flush"], wait=safe_cfg["wait"]),
    )
    print("WAS RUNNING")
    t = Thread(target=start_program)
    t.start()


####################
# PUMP SETUP AND CONFIGURATION
####################
def switch_on():
    """Turn pump ON."""
    if GPIO:
        GPIO.output(PUMP_GPIO, GPIO.HIGH)  # on
    cache.set("running", True)
    run_mode = "automatic" if cache.get("run_auto") else "manual"  # only for logging
    logger.warning(f"Bomba ON | Mode: {run_mode}")


def switch_off():
    """Turn pump OFF."""
    if GPIO:
        GPIO.output(PUMP_GPIO, GPIO.LOW)  # off

    cache.set_many(
        (("cycle_ends_in", None), ("next_cycle_at", None), ("running", False))
    )
    run_mode = "automatic" if cache.get("run_auto") else "manual"  # only for logging
    logger.warning(f"Bomba OFF |  Mode: {run_mode}")


# PUMP CYCLE
def pump_cycle(cycle: int, period: int):
    """Define how long pump is ON in order to full the fish tank.

    cycle: pump flush time
    period: wait time + close time
    """
    # Turn on the pump
    started = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    cache.set("total_loops", cache.get("total_loops") + 1)
    switch_on()
    # cycle_ends_in = to_js_time(cycle, "auto")
    cache.set("cycle_ends_in", to_js_time(cycle, "auto"))
    socketio.emit(
        "automatic_program",
        {
            "data": "Server generated event",
            "running": cache.get("running"),
            "cycle_fase": cache.set("cycle_fase", "flush"),
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
            # cache.set("cycle_ends_in", to_js_time(period, "auto"))
            ended = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            # Write information to logging file
            logger.warning(
                f"""Programa actual [{cache.get("total_loops")}]: Iniciat: {started} | Acabat: {ended}"""  # noqa
            )
        else:  # Ignore previous. Pump is already off
            logger.warning(
                f"Programa automàtic: Iniciat {started} va ser tancat obligat per l'usuari"
            )


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
        flash(f"{greeting()}, benvingut {session['username']}", "info")
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
                # Set up flag for safe fish mode
                _safe_fish_flag(True)

        elif request.form.get("action", False) == "stop":
            switch_off()  # TODO: Must be checked first
            # Remove counters/timers and stop background thread
            cache.set_many(
                (
                    ("running", False),
                    ("cycle_ends", None),
                    ("cycle_ends_in", None),
                    ("run_auto", False),
                )
            )
            exit_thread.set()
            # Set up flag for safe fish mode
            _safe_fish_flag(False)
        ###########################
        # MANUAL MODE
        ###########################
        if request.form.get("manual", False):  # MUST BE CHECK IF CAN BE elif and not if
            if request.form["manual"] == "start_manual":
                cache.set_many(
                    (
                        ("started_at", to_js_time(run_type="manual")),
                        ("run_manual", True),
                    )
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
    config = config_from_file(ROOT)
    logs = get_logs()

    return render_template(
        "app.html", flush=flush, wait=wait, close=close, config=config, logs=logs
    )


####################
# LOGS ROUTES
####################
def get_logs():
    """Route to see all zip files available to download."""
    logs_folder = glob(f"{app.config['LOGS_FOLDER']}/*.log*")
    # get only the file name and the size of it excluding the path.
    # Create a list of tuples sorted by file name
    logs_folder = sorted([os.path.basename(f) for f in logs_folder])
    return [{"id_": i, "name": file_} for i, file_ in enumerate(logs_folder)]


@app.route("/read_log/<log>")
def read_log(log):
    """Open a log file and return it to a html page."""
    file_ = os.path.join(app.config["LOGS_FOLDER"], log)
    with open(file_, "r") as f:
        log_text = [
            f"""<tr>
          <th scope="row">{idx}</th>
          <td>{line.split("||")[0]}</td>
          <td>{line.split("||")[1]}</td>
        </tr>"""
            for idx, line in enumerate(f.readlines())
        ]
    return render_template("_read_log.html", tbody="".join(log_text))


@app.route("/download_log/<log>")
def download_log(log):
    """Download a log file."""
    return send_from_directory(app.config["LOGS_FOLDER"], log)


####################
# AUTHENTICATION AND SYSTEM STUFF
####################
@app.route("/settings", methods=["POST"])
def settings():
    save_config_to_file(request.form.to_dict())
    flash("S'ha actualitzat la configuració", "info")
    return redirect("respi")


@app.route("/login", methods=["GET", "POST"])
def login():
    """User login page."""
    if request.method == "POST":
        password = request.form.get("password", None)
        session["username"] = request.form.get("username", None)
        if check_password(password):
            logger.warning(f"{request.form.get('username')} connectado")
            flash(f"{greeting()}! Benvingut {session['username']}", "info")
            return redirect(url_for("respi"))
        flash("Contrasenya incorrecta", "danger")
    return render_template("login.html")


@app.route("/logout")
def logout():
    """Log out user from browser session."""
    session["auth"] = False
    logger.warning(f"{session['username']} va sortir.")
    flash(f"Adeu!! {session['username']}", "info")
    return redirect(url_for("landing"))


@app.route("/turn_off")
def turn_off():
    """Turn off controller board."""
    _safe_fish_flag(False)
    subprocess.Popen(["sudo", "shutdown", "now"], shell=True)
    flash(f"Apagar el sistema... Espereu si us plau", "info")
    return redirect(url_for("landing"))


@app.route("/restart")
def restart():
    """Restart controller board."""
    _safe_fish_flag(False)
    subprocess.Popen(["sudo", "reboot"], shell=True)
    flash(
        f"""Reinicieu el sistema, espereu si us plau.
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
            "generating_files": cache.get("generating_files"),
            "total_loops": cache.get("total_loops"),
            "auto_run_since": cache.get("auto_run_since"),
        }
    )


@app.route("/user_time/<local_time>", methods=["GET", "POST"])
def update_time(local_time):
    """Get user local time to update server time."""
    return cache.set("user_time", local_time)


if __name__ == "__main__":
    socketio.run(app, debug=True, host="0.0.0.0")
