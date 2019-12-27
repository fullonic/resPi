"""Application backend logic."""

import os
import shutil
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

from scripts.converter import ExperimentCycle
from scripts.stats import ResumeDataFrame
from scripts.error_handler import checker

from scripts.utils import (
    to_mbyte,
    delete_zip_file,
    to_js_time,
    check_extensions,
    SUPPORTED_FILES,
    greeting,
    config_from_file,
    save_config_to_file

)

ROOT = os.path.dirname(os.path.abspath(__file__))  # app root dir
# App basic configuration
config = {
    "SECRET_KEY": "NONE",
    "CACHE_TYPE": "simple",
    "CACHE_DEFAULT_TIMEOUT": 0,
    # "CACHE_ARGS": ["test", "Anna", "DIR"],
    "UPLOAD_FOLDER": f"{ROOT}/static/uploads",
    "LOGS_FOLDER": f"{ROOT}/logs",
    "LOGS_MB_SIZE": 24578,
    "LOGS_BACKUP": 10,
    "ZIP_FOLDER": f"{ROOT}/static/uploads/zip_files",
}  # UNIT: minutes

# DEFINE RASPBERRY PI PINS NUMBERS AND API FUNCTIONS
if GPIO is not None:
    GPIO.setmode(GPIO.BCM)  # Use GPIO Numbers
    PUMP_GPIO = 26  # Digital input to the relay
    GPIO.setup(PUMP_GPIO, GPIO.OUT)  # GPIO Assign mode


# DEFINE APP
app = Flask(__name__)
app.config.from_mapping(config)
_active_threads = {}
exit_thread = Event()
# Setup cache
cache = Cache(app)
# TODO: user cache.set_many() to provide all default cache values
cache.set("running", False)  # By default pump is off
cache.set("run_auto", False)
cache.set("run_manual", False)

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
handler.setFormatter(logging.Formatter("%(asctime)s - %(name)s - %(message)s"))
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
    cache.set("running", False)
    cache.set("cycle_ends_in", None)
    cache.set("next_cycle_at", None)
    run_mode = "automatic" if cache.get("run_auto") else "manual"  # only for logging
    logger.warning(f"Pump is off |  Mode: {run_mode}")


# PUMP CYCLE
def pump_cycle(cycle, period):
    """Define how long pump is ON in order to full the fish tank."""
    # Turn on the pump
    started = datetime.now()
    switch_on()
    cache.set("cycle_ends_in", to_js_time(cycle, "auto"))
    socketio.emit(
        "automatic_program",
        {
            "data": "Server generated event",
            "running": cache.get("running"),
            "run_auto": cache.get("running"),
            "cycle_ends_in": cache.get("cycle_ends_in"),
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
            ended = datetime.now()
            # print(f"Current automatic program: Started {str(started)} | Ended: {str(ended)}")
            # Write information to logging file
            logger.warning(
                f"Current automatic program: Started {str(started)} | Ended: {str(ended)}"
            )
        else:  # Ignore previous. Pump is already off
            logger.warning(
                f"Automatic program: Started {str(started)} was closed forced by user"
            )


####################
# BACKGROUND TASKS
####################
# USER DEFINED PROGRAM
def start_program(app=None):
    """Start a new background thread to run the user program."""
    logger.warning("""Starting a new background thread to run the user program.""")
    # program()
    """User defined task.

    Creates a periodic task using user form input.
    """
    user_program = cache.get("user_program")
    # Turn the pump on every x seconds
    period = (user_program.get("close") + user_program.get("wait")) * UNIT
    cycle = user_program.get("flush") * UNIT  # Run the pump for the time of x seconds
    while cache.get("run_auto"):
        pump_cycle(cycle, period)
        if not exit_thread.wait(timeout=period):
            continue
        # if not cache.get("run_auto"):
        #     break
        # time.sleep(period)
    else:
        return False


def process_excel_files(flush, wait, close, uploaded_excel_files, plot):
    """Start a new thread to process excel file uploaded by the user."""
    # Confirm headers
    # Loop throw all uploaded files and clean the data set
    save_converted = False
    total_files = len(uploaded_excel_files)
    logger.warning(f"A total of {total_files} files received")
    for i, file_path in enumerate(uploaded_excel_files):
        # generate_data(flush, wait, close, file_path, new_column_name, plot, plot_title)
        experiment = ExperimentCycle(
            flush, wait, close, file_path, "Date &Time [DD-MM-YYYY HH:MM:SS]"
        )
        if save_converted:
            experiment.original_file.save()
        resume = ResumeDataFrame(experiment)
        resume.generate_resume()
        if plot:
            experiment.create_plot()
        resume.save()

        # TODO: add flag to save or not all converted file to excel

        resume = ResumeDataFrame(experiment)

        logger.warning(f"Task concluded {i+1}/{total_files}")
        socketio.emit(
            "processing_files",
            {"generating_files": True, "msg": f"fitxers processats {i+1}/{total_files}"},
            namespace="/resPi",
        )
    cache.set("generating_files", False)
    socketio.emit(
        "processing_files", {"generating_files": False, "msg": ""}, namespace="/resPi"
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
                session["user_program"] = [flush, wait, close]
                # Create a register of the started thread
                global _active_threads
                t = Thread(target=start_program)
                t_name = t.getName()
                _active_threads[t_name] = t  # noqa
                logger.warning(f"STARTED NEW {_active_threads}")
                exit_thread.clear()  # set all thread flags to false
                t.start()  # start a fresh new thread with the current program
        elif request.form.get("action", False) == "stop":
            switch_off()  # TODO: Must be checked first
            cache.set("running", False)  # Turn off red led
            # Remove counters/timers
            cache.set("cycle_ends", None)
            cache.set("next_cycle_at", None)
            cache.set("run_auto", False)  # Stop background thread
            exit_thread.set()
            logger.warning(f"AFTER SET {_active_threads}")
        ###########################
        # MANUAL MODE
        ###########################
        if request.form.get("manual", False):
            if request.form["manual"] == "start_manual":
                cache.set("run_manual", True)
                cache.set("started_at", to_js_time(run_type="manual"))
                switch_on()
            else:
                switch_off()
                cache.set("run_manual", False)

    # Populate form inputs with last inserted program or from config file values
    if not cache.get("user_program"):
        config = config_from_file()["pump_control_config"]
        flush = int(config["flush"])
        wait = int(config["wait"])
        close = int(config["close"])
    else:
        flush = cache.get("user_program")["flush"]
        wait = cache.get("user_program")["wait"]
        close = cache.get("user_program")["close"]

    logger.warning(f"2 AFTER SET {_active_threads}")

    return render_template("app.html", flush=flush, wait=wait, close=close)


@app.route("/settings", methods=["POST", "GET"])
def settings():
    config = config_from_file()
    if request.method == "POST":
        config = save_config_to_file(request.form.to_dict())
    return render_template("settings.html", config=config)


@app.route("/excel_files", methods=["POST", "GET"])
def excel_files():
    """User GUI for upload and deal with excel files."""
    if request.method == "POST":
        # Get basic information about the data set
        flush = int(request.form.get("flush"))
        wait = int(request.form.get("wait"))
        close = int(request.form.get("close"))
        plot = True if request.form.get("plot") == "yes" else False

        # TODO: This should be added to the file upload GUI form
        cache.set("new_column_name", "evolucio_oxigen/temps")
        cache.set("plot_title", "Evolució de l’oxigen")

        cache.set("generating_files", True)
        # Save file to the system
        # NOTE: Must check for extensions
        files = request.files.getlist("files")
        # Contains a list of all uploaded file in a single uploaded request
        uploaded_excel_files = []
        for file_ in files:
            # Generate the folder name
            time_stamp = datetime.now().strftime(f"%Y_%m_%d_%H_%M_%S")
            filename, ext = file_.filename.split(".")
            if not check_extensions(ext):
                flash(
                    f"El tipus de fitxer {ext} no és compatible. Seleccioneu un tipus de fitxer {SUPPORTED_FILES}",  # noqa
                    "danger",
                )
                return redirect("excel_files")
            folder_name = f"{filename}_{time_stamp}"
            project_folder = os.path.join(app.config["UPLOAD_FOLDER"], folder_name)
            try:
                os.mkdir(project_folder)
            except FileExistsError:
                project_folder = os.path.join(app.config["UPLOAD_FOLDER"], f"{folder_name}_1")
                os.mkdir(project_folder)
            # Here filename complete with extension
            filename = file_.filename
            file_path = os.path.join(project_folder, filename)
            file_.save(file_path)
            # CHECK HEADERS
            check = checker(file_path).match()
            print(f"{check=}")
            if check is True:
                print("MATCH")
            else:
                # TODO: Return flash message warning and abort
                for msg in check:
                    msg += " "
                flash(
                    check,
                    "danger",
                )
                # Removes folder and file that doesn't match headers
                shutil.rmtree(os.path.dirname(file_path))

                return redirect("excel_files")
            # save the full path of the saved file
            uploaded_excel_files.append(file_path)

        t = Thread(
            target=process_excel_files, args=(flush, wait, close, uploaded_excel_files, plot)
        )
        t.start()

        # Fixed
        session["excel_config"] = {"flush": flush, "wait": wait, "close": close}
        flash(
            f"""El fitxer s'ha carregat correctament. Quan totes les dades s’hagin processat,
            estaran disponibles a la secció de descàrregues..""",
            "info",
        )
        return redirect("excel_files")

    return render_template("excel_files.html", config=session.get("excel_config", None))


####################
# DOWNLOAD ROUTES
####################
@app.route("/downloads", methods=["GET"])
def downloads():
    """Route to see all zip files available to download."""
    print(f"{cache.get_dict()=}")
    zip_folder = glob(f"{app.config['ZIP_FOLDER']}/*.zip")
    # get only the file name and the size of it excluding the path.
    # Create a list of tuples sorted by file name
    zip_folder = sorted(zip_folder, key=lambda x: os.path.getmtime(x))[::-1]

    # TODO: Convert to namedtuple or class
    zip_folder = [
        (
            os.path.basename(f),
            os.path.getsize(f),
            datetime.utcfromtimestamp(os.path.getmtime(f)),
        )
        for f in zip_folder
    ]
    zip_files = [
        {
            "id_": i,
            "name": file_[0],
            "created": file_[2].strftime("%Y/%m/%d %H:%M"),
            "size": to_mbyte(file_[1]),
        }
        for i, file_ in enumerate(zip_folder)
    ]

    return render_template("download.html", zip_files=zip_files)


@app.route("/get_file/<file_>", methods=["GET"])
def get_file(file_):
    """Download a zip file based on file name."""
    return send_from_directory(app.config["ZIP_FOLDER"], file_)


@app.route("/remove_file/<file_>", methods=["GET"])
def remove_file(file_):
    """Delete a zip file based on file name."""
    location = os.path.join(app.config["ZIP_FOLDER"], file_)
    print(location)
    delete_zip_file(location)
    return redirect(url_for("downloads"))


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
    print("STATUS ", cache.get("started_at"))
    return jsonify(
        {
            "running": cache.get("running"),
            "run_auto": cache.get("run_auto"),
            "run_manual": cache.get("run_manual"),
            "started_at": cache.get("started_at"),
            "cycle_ends_in": cache.get("cycle_ends_in"),
            "next_cycle_at": cache.get("next_cycle_at"),
            "generating_files": cache.get("generating_files"),
        }
    )


if __name__ == "__main__":
    socketio.run(app, debug=True, host="0.0.0.0")
