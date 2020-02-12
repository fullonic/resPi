"""Application backend logic."""

import webbrowser
import sys
import os
import shutil
import time
import subprocess
import logging
from glob import glob
from logging.handlers import RotatingFileHandler
from functools import wraps
from threading import Thread, Event
from datetime import datetime
from functools import partial  # noqa maybe can be used on save files

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
from engineio.async_drivers import gevent  # noqa

from scripts.converter import ExperimentCycle, ControlFile
from scripts.stats import ResumeDataFrame, Control
from scripts.error_handler import checker

from scripts.utils import (
    to_mbyte,
    delete_zip_file,
    to_js_time,
    check_extensions,
    SUPPORTED_FILES,
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
    # "CACHE_ARGS": ["test", "Anna", "DIR"],
    "UPLOAD_FOLDER": f"{ROOT}/static/uploads",
    "LOGS_FOLDER": f"{ROOT}/logs",
    "LOGS_MB_SIZE": 24578,
    "LOGS_BACKUP": 10,
    "ZIP_FOLDER": f"{ROOT}/static/uploads/zip_files",
}  # UNIT: minutes

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
socketio = SocketIO(app, async_mode="gevent")

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


def show_preview(flush, wait, close, file_):
    """Proxy function to generate a global plot preview."""
    file_path = os.path.join(f"{app.config['UPLOAD_FOLDER']}/preview", file_.filename)
    file_.save(file_path)

    ExperimentCycle(flush, wait, close, file_path)
    os.remove(file_path)


####################
# BACKGROUND TASKS
####################
def process_excel_files(
    flush, wait, close, uploaded_excel_files, plot, ignore_loops: list = None
):
    """Start a new thread to process excel file uploaded by the user."""
    # Loop throw all uploaded files and clean the data set
    save_converted = False  # NOTE: REMOVE AND GET INFO FROM CONFIG FILE

    # CALCULATE BLANKS
    control_file_1 = os.path.join(os.path.dirname(uploaded_excel_files[0]), "C1.txt")
    control_file_2 = os.path.join(os.path.dirname(uploaded_excel_files[0]), "C2.txt")

    for c in [control_file_1, control_file_2]:
        C = ControlFile(flush, wait, close, c)
        C_Total = Control(C)
        C_Total.get_bank()
    control = C_Total.calculate_blank()
    print(f"Valor 'Blanco' {control}")

    ######################
    #
    ######################
    now = time.perf_counter()
    total_files = len(uploaded_excel_files)
    logger.warning(f"A total of {total_files} files received")
    for i, file_path in enumerate(uploaded_excel_files):
        # generate_data(flush, wait, close, file_path, new_column_name, plot, plot_title)
        experiment = ExperimentCycle(flush, wait, close, file_path, ignore_loops)
        if save_converted:
            experiment.original_file.save()
        resume = ResumeDataFrame(experiment)
        resume.generate_resume(control)
        if plot:
            experiment.create_plot()
        resume.save()

        resume = ResumeDataFrame(experiment)

        logger.warning(f"Task concluded {i+1}/{total_files}")
        socketio.emit(
            "processing_files",
            {"generating_files": True, "msg": f"fitxers processats {i+1}/{total_files}",},
            namespace="/resPi",
        )
    cache.set("generating_files", False)
    socketio.emit(
        "processing_files", {"generating_files": False, "msg": ""}, namespace="/resPi"
    )
    print(f"Total time {time.perf_counter() - now}")


####################
# APP ROUTES
####################
@app.route("/", methods=["GET"])
def landing():
    """Endpoint dispatcher to redirect user to the proper route."""
    # Check if user is authenticated
    return redirect(url_for("excel_files"))


@app.route("/excel_files", methods=["POST", "GET"])
def excel_files():
    """User GUI for upload and deal with excel files."""
    session["excel_config"] = config_from_file()["file_cycle_config"]

    if request.method == "POST":
        cache.set("generating_files", True)
        # Get all uploaded files and do validation
        data_file = request.files.get("data_file")
        control_file_1 = request.files.get("control_file_1")
        control_file_2 = request.files.get("control_file_2")
        for f in [data_file, control_file_1, control_file_2]:
            filename, ext = f.filename.split(".")
            if not check_extensions(ext):
                flash(
                    f"El tipus de fitxer {ext} no és compatible. Seleccioneu un tipus de fitxer {SUPPORTED_FILES}",  # noqa
                    "danger",
                )
                return redirect("excel_files")

        # Get basic information about the data set
        filename = data_file.filename.split(".")[0]
        flush = int(request.form.get("flush"))
        wait = int(request.form.get("wait"))
        close = int(request.form.get("close"))
        plot = True if request.form.get("plot") else False  # if generate or no loop plots
        try:
            ignore_loops = [int(loop) for loop in request.form["ignore_loops"].split(",")]
        except ValueError:  # If user didn't insert any value
            ignore_loops = None

        # Show preview plot if user wants
        if request.form.get("experiment_plot"):
            show_preview(flush, wait, close, data_file)
            cache.set("generating_files", False)
            return redirect(url_for("show_global_plot"))
        # Contains a list of all uploaded file in a single uploaded request
        uploaded_excel_files = []
        # Generate the folder name
        time_stamp = datetime.now().strftime(f"%d_%m_%Y_%H_%M_%S")

        folder_name = f"{filename}_{time_stamp}"
        project_folder = os.path.join(app.config["UPLOAD_FOLDER"], folder_name)
        try:
            os.mkdir(project_folder)
        except FileExistsError:
            project_folder = os.path.join(app.config["UPLOAD_FOLDER"], f"{folder_name}_1")
            os.mkdir(project_folder)
        # Here filename complete with extension
        control_file_1.filename = "C1.txt"
        control_file_2.filename = "C2.txt"
        # Save all files into project folder
        files_list = [data_file, control_file_1, control_file_2]
        for file_ in files_list:
            file_path = os.path.join(project_folder, file_.filename)
            file_.save(file_path)
        # CHECK HEADERS
        check = checker(file_path).match()
        if check is not True:
            for msg in check:
                msg += " "
            flash(check, "danger")
            # Removes folder and file that doesn't match headers
            shutil.rmtree(os.path.dirname(file_path))
            return redirect("excel_files")
        # save the full path of the saved file
        uploaded_excel_files.append(os.path.join(project_folder, data_file.filename))
        t = Thread(
            target=process_excel_files,
            args=(flush, wait, close, uploaded_excel_files, plot, ignore_loops),
        )
        t.start()

        # Fixed
        session["excel_config"] = {"flush": flush, "wait": wait, "close": close}
        flash(
            f"""El fitxer s'ha carregat correctament. Quan totes les dades s’hagin processat,
            estaran disponibles a la secció de descàrregues..""",
            "info",
        )
        # session["ignore_loops"] = None
        return redirect("excel_files")

    config = session.get("excel_config")
    config["ignore_loops"] = session.get("ignore_loops")
    return render_template("excel_files.html", config=config)


@app.route("/show_global_plot")
def show_global_plot():
    return render_template("global_graph_preview.html")


####################
# DOWNLOAD ROUTES
####################
@app.route("/downloads", methods=["GET"])
def downloads():
    """Route to see all zip files available to download."""
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
    delete_zip_file(location)
    return redirect(url_for("downloads"))


@app.route("/settings", methods=["POST", "GET"])
def settings():
    """User define app settings."""
    config = config_from_file()
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


@app.route("/status", methods=["GET"])
def get_status():
    """Return information about the different components of the system."""
    return jsonify(
        {
            "running": cache.get("running"),
            "run_auto": cache.get("run_auto"),
            "run_manual": cache.get("run_manual"),
            "started_at": cache.get("started_at"),
            "cycle_ends_in": cache.get("cycle_ends_in"),
            "next_cycle_at": cache.get("next_cycle_at"),
            "generating_files": cache.get("generating_files"),
            "total_loops": cache.get("total_loops"),
            "auto_run_since": cache.get("auto_run_since"),
        }
    )


@app.route("/remove_loops", methods=["POST"])
def remove_loops():
    """Save user selected loops to be deleted on user session"""
    # session["ignore_loops"] = [int(loop) for loop in request.form["ignore_loops"].split(",")]
    session["ignore_loops"] = request.form["ignore_loops"]
    return redirect(url_for("excel_files"))


@app.route("/user_time/<local_time>", methods=["GET", "POST"])
def update_time(local_time):
    """Get user local time to update server time."""
    print(local_time)
    return redirect(url_for("login"))


if __name__ == "__main__":
    port = 5000
    # webbrowser.open(f"http://localhost:{port}/excel_files")
    # socketio.run(app, debug=False, host="0.0.0.0", port=port)
    socketio.run(app, debug=True, host="0.0.0.0", port=port)
