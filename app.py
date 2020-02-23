"""Application backend logic."""

import logging
import os
import shutil
import sys
import time
import webbrowser
from datetime import datetime, timedelta
from functools import partial  # noqa maybe can be used on save files
from glob import glob
from logging.handlers import RotatingFileHandler
from pathlib import Path
from threading import Event, Thread

from engineio.async_drivers import gevent  # noqa
from flask import (
    Flask,
    flash,
    jsonify,
    redirect,
    render_template,
    request,
    send_from_directory,
    session,
    url_for,
)
from flask_caching import Cache
from flask_debugtoolbar import DebugToolbarExtension
from flask_socketio import SocketIO
from werkzeug.security import check_password_hash, generate_password_hash  # noqa

from core import ControlFile, ExperimentCycle, ResumeControl, ResumeDataFrame
from core.error_handler import checker
from core import parser
from core.utils import (
    SUPPORTED_FILES,
    check_extensions,
    config_from_file,
    delete_zip_file,
    global_plots,
    save_config_to_file,
    to_mbyte,
)

# ROOT = os.path.dirname(os.path.abspath(__file__))  # app root dir
# print(f"{ROOT=}")
ROOT = Path(__file__).resolve().parent  # app root dir
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
    "DEBUG_TB_INTERCEPT_REDIRECTS": False,
}  # UNIT: minutes

# DEFINE APP
if getattr(sys, "frozen", False):
    template_folder = os.path.join(sys._MEIPASS, "templates")
    static_folder = os.path.join(sys._MEIPASS, "static")
    app = Flask(__name__, template_folder=template_folder, static_folder=static_folder)
else:
    template_folder = Path("templates").resolve()
    app = Flask(__name__)


app.config.from_mapping(config)
exit_thread = Event()

# app.debug = True
toolbar = DebugToolbarExtension(app)

# Setup cache
cache = Cache(app)
cache.set_many(
    (
        ("run_manual", False),
        ("run_auto", False),
        ("running", False),
        ("ignored_loops", {"C1": [], "Experiment": [], "C2": []}),
    )
)


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

logger.addHandler(handler)


####################
# BACKGROUND TASKS
####################
def process_excel_files(
    flush, wait, close, uploaded_excel_files, plot, ignore_loops: dict = None
):
    """Start a new thread to process excel file uploaded by the user."""
    # Loop throw all uploaded files and clean the data set
    save_converted = False  # NOTE: REMOVE AND GET INFO FROM CONFIG FILE

    # CALCULATE BLANKS
    control_file_1 = os.path.join(os.path.dirname(uploaded_excel_files[0]), "C1.txt")
    control_file_2 = os.path.join(os.path.dirname(uploaded_excel_files[0]), "C2.txt")
    ignore_loops = cache.get("ignored_loops")

    for idx, c in enumerate([control_file_1, control_file_2]):
        C = ControlFile(
            flush,
            wait,
            close,
            c,
            file_type=f"control_{idx + 1}",
            ignore_loops=ignore_loops,
        )
        C_Total = ResumeControl(C)
        C_Total.get_bank()
        if plot:
            C.create_plot()

    control = C_Total.calculate_blank()
    print(f"Valor 'Blanco' {control}")

    ######################
    #
    ######################
    now = time.perf_counter()
    total_files = len(uploaded_excel_files)
    for i, data_file in enumerate(uploaded_excel_files):
        experiment = ExperimentCycle(
            flush,
            wait,
            close,
            data_file,
            ignore_loops=ignore_loops,
            file_type="Experiment",
        )
        if save_converted:
            experiment.original_file.save()
        resume = ResumeDataFrame(experiment)
        resume.generate_resume(control)
        resume.save()
        if plot:
            experiment.create_plot()
            global_plots(
                flush,
                wait,
                close,
                files=resume.experiment_files,
                preview_folder=Path(template_folder) / "previews",
                keep=True,
                folder_dst=resume.experiment.original_file.folder_dst,
            )
        resume.zip_folder()

        # logger.warning(f"Task concluded {i+1}/{total_files}")
        print("Tasca conclosa")
    cache.set("generating_files", False)
    print(f"Processament de temps total {round(time.perf_counter() - now, 3)} segons")


####################
# APP ROUTES
####################
@app.route("/", methods=["GET"])
def landing():
    """Endpoint dispatcher to redirect user to the proper route."""
    return redirect(url_for("excel_files"))


@app.route("/excel_files", methods=["POST", "GET"])
# @cache.cached(timeout=15000, key_prefix="main_page")
def excel_files():
    """User GUI for upload and deal with excel files."""
    session["excel_config"] = config_from_file()["file_cycle_config"]
    ignore_loops = cache.get("ignored_loops")
    if request.method == "POST":
        cache.set("generating_files", True)
        # IGNORED
        C1_ignore = {"C1": [_ for _ in request.form.get("c1_ignore_loops").split(",")]}
        Data_ignore = {
            "Experiment": [_ for _ in request.form.get("data_ignore_loops").split(",")]
        }
        C2_ignore = {"C2": [_ for _ in request.form.get("c2_ignore_loops").split(",")]}
        ignore_loops = {**C1_ignore, **Data_ignore, **C2_ignore}
        cache.set("ignored_loops", ignore_loops)
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
        plot = (
            True if request.form.get("plot") else False
        )  # if generate or no loop plots
        # Show preview plot if user wants
        control_file_1.filename = "C1.txt"
        control_file_2.filename = "C2.txt"
        if request.form.get("experiment_plot"):
            global_plots(
                flush,
                wait,
                close,
                [control_file_1, data_file, control_file_2],
                preview_folder=f"{app.config['UPLOAD_FOLDER']}/preview",
                keep=False,
            )
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
            project_folder = os.path.join(
                app.config["UPLOAD_FOLDER"], f"{folder_name}_1"
            )
            os.mkdir(project_folder)
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
            args=(flush, wait, close, uploaded_excel_files, plot),
        )
        t.start()

        # Fixed
        session["excel_config"] = {"flush": flush, "wait": wait, "close": close}
        flash(
            f"""Els fitxers s'ha carregat. Quan totes les dades s’hagin processat,
            estaran disponibles a la secció Descàrregues..""",
            "info",
        )
        cache.set("ignored_loops", {"C1": [], "Experiment": [], "C2": []})
        return redirect("excel_files")

    exp_config = session.get("excel_config")
    # exp_config["ignore_loops"] = cache.get("ignored_loops")
    exp_config["ignore_loops"] = (
        cache.get("ignored_loops")
        if cache.get("ignored_loops")
        else {"C1": " ", "Experiment": " ", "C2": " "}
    )

    config = config_from_file()
    return render_template("excel_files.html", exp_config=exp_config, config=config)


@app.route("/show_global_plot")
def show_global_plot():
    plots = [
        {"name": f.name.split(".")[0], "path": f"previews/{f.name}"}
        for f in Path(Path().resolve() / "templates/previews").glob("*.html")
    ]
    return render_template("global_graph_preview.html", plots=plots)


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
    zip_folder = (
        (
            os.path.basename(f),
            os.path.getsize(f),
            datetime.utcfromtimestamp(os.path.getmtime(f)) + timedelta(hours=1),
        )
        for f in zip_folder
    )
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


@app.route("/downloads/all")
def download_all():
    all_zipped = shutil.make_archive(
        app.config["ZIP_FOLDER"], "zip", app.config["ZIP_FOLDER"]
    )
    return send_from_directory(Path(all_zipped).parent, Path(all_zipped).name)


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


@app.route("/remove_file/all", methods=["GET"])
def remove_all_files():
    """Delete a zip file based on file name."""
    for f in Path(app.config["ZIP_FOLDER"]).glob("*.zip"):
        delete_zip_file(f)
    return redirect(url_for("downloads"))


@app.route("/settings", methods=["POST", "GET"])
def settings():
    save_config_to_file(request.form.to_dict())
    flash("S'ha actualitzat la configuració", "info")
    cache.delete("main_page")
    return redirect("excel_files")


@app.route("/help", methods=["GET"])
def help():
    help_page = parser("https://gitlab.com/fullonic/resPi/-/raw/master/README.md")
    return render_template("help.html", help_page=help_page)


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
# API ROUTES
####################
@app.route("/status", methods=["GET"])
def get_status():
    """Return information about the different components of the system."""
    return jsonify({"generating_files": cache.get("generating_files"),})


@app.route("/ignore_loops/<data>", methods=["POST"])
def ignore_loops(data: str) -> dict:
    """Add loops from multiple data sets to be ignored.

    data:
    key: DF name: C1, Experiment, C2
    value: list of loops to be ignored
    """
    if request.method == "POST":
        if cache.get("ignored_loops") is None:
            cache.set("ignored_loops", {})
        fname, loops = data.split(":")
        try:
            loops = set([int(l) for l in loops.split(",") if l.isdigit()])
            print(f"Ignorar 'loops': {loops} | {fname}")

        except ValueError:
            return "error", 400
        # Update cache information about ignored loops
        update = cache.get("ignored_loops")
        update.update({fname: list(loops)})
        cache.set("ignored_loops", update)
        return "ok", 201


@app.route("/ignored_loops", methods=["GET"])
def ignored_loops():
    return jsonify(cache.get("ignored_loops"))


if __name__ == "__main__":
    port = 5000
    print("*" * 70)
    with open("logo.txt") as logo:
        print(logo.read())
    print("""Benvingut a l'aplicació de "resPi Converter" """)
    print("*" * 70)
    print("\n")
    print("Carregant l'aplicació ...")
    webbrowser.open(f"http://localhost:{port}")
    print("\n")
    print(
        "Si l'aplicació no s'obre automàticament, introduïu la següent URL al navegador"
    )
    print(f"http://localhost:{port}")
    print("\n")
    print("*" * 70)
    print("Avís: tancant aquesta finestra es tancarà l’aplicació")
    print("*" * 70)
    socketio.run(app, debug=False, host="0.0.0.0", port=port)
    # socketio.run(app, debug=True, host="0.0.0.0", port=port)
