"""Application backend logic."""

import os
import shutil
import sys
import time
import webbrowser
import filecmp
from datetime import datetime, timedelta
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

# from flask_debugtoolbar import DebugToolbarExtension
from flask_socketio import SocketIO

from core.converter import ControlFile, ExperimentCycle
from core.resume import ResumeControl, ResumeDataFrame, TearDown
from core.error_handler import checker
from core.parse_help_page import parser
from core.utils import (
    SUPPORTED_FILES,
    check_extensions,
    config_from_file,
    delete_zip_file,
    global_plots,
    save_config_to_file,
    to_mbyte,
)

ROOT = Path(__file__).resolve().parent  # app root dir
# App basic configuration
config = {
    "SECRET_KEY": "NONE",
    "CACHE_TYPE": "simple",
    "CACHE_DEFAULT_TIMEOUT": 0,
    # "CACHE_ARGS": ["test", "Anna", "DIR"],
    "UPLOAD_FOLDER": f"{ROOT}/static/uploads",
    "FILES_PREVIEW_FOLDER": f"{ROOT}/static/uploads/preview",
    "GRAPHICS_PREVIEW_FOLDER": f"{ROOT}/templates/previews",
    "ZIP_FOLDER": f"{ROOT}/static/uploads/zip_files",
    "DEBUG_TB_INTERCEPT_REDIRECTS": False,
}  # UNIT: minutes

# DEFINE APP
if getattr(sys, "frozen", False):
    template_folder = os.path.join(sys._MEIPASS, "templates")  # noqa
    static_folder = os.path.join(sys._MEIPASS, "static")  # noqa
    app = Flask(__name__, template_folder=template_folder, static_folder=static_folder)
else:
    template_folder = Path("templates").resolve()
    app = Flask(__name__)


app.config.from_mapping(config)
exit_thread = Event()

# app.debug = True
# toolbar = DebugToolbarExtension(app)

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


####################
# MULTI PROCESSOR TASK
####################
def save_loop_file(experiment):  # TODO: SAVE INDIVIDUAL LOOPS FASTER WIP
    for k, loop in enumerate(experiment.df_loop_generator, start=1):
        if experiment.file_type == "Experiment":
            experiment.save(loop, name=str(k))
        else:
            experiment.save(loop, name=f"{experiment.original_file.fname}_{str(k)}")


def save_loop_graph(experiment):  # TODO: CREATE INDIVIDUAL LOOPS FASTER WIP
    """Generate individual graphs for loop of each uploaded file."""
    print(f"CREATING PLOT: {experiment.original_file.fname}")
    experiment.create_plot()


def compare_files(experiment_files, preview_experiment_files, project_folder, times={}):
    k_map = {"C1.txt": "C1.html", "C2.txt": "C2.html"}
    for uploaded, preview in zip(experiment_files, preview_experiment_files):
        if not filecmp.cmp(preview, uploaded):
            # User uploaded a new file after preview global plot
            experiment = ExperimentCycle(
                **times, original_file=uploaded, file_type="Global grafic"
            )
            experiment.experiment_plot()
        else:
            # move html file from templates preview into project folder
            html_file = Path(app.config["GRAPHICS_PREVIEW_FOLDER"]) / k_map.setdefault(
                uploaded.name, "Experiment.html"
            )
            shutil.move(str(html_file), str(project_folder))


####################
# BACKGROUND TASKS
####################
def process_excel_files(
    flush, wait, close, uploaded_excel_files, plot, ignore_loops: dict = None
):
    """Start a new thread to process excel file uploaded by the user."""
    # Loop throw all uploaded files and clean the data set
    config = config_from_file()
    project_folder = Path(uploaded_excel_files[0]).parent
    if plot:
        experiment_files = sorted([f for f in Path(project_folder).glob("*.txt")])
        preview_experiment_files = sorted(
            [f for f in Path(app.config["FILES_PREVIEW_FOLDER"]).glob("*.txt")]
        )
        times = {"flush": flush, "wait": wait, "close": close}
        if preview_experiment_files:
            print("HERE, preview_experiment_files")
            compare_files(
                experiment_files, preview_experiment_files, project_folder, times=times,
            )
        else:
            print("global_plots")
            global_plots(
                flush,
                wait,
                close,
                experiment_files,
                preview_folder=f"{app.config['UPLOAD_FOLDER']}/preview",
                keep=True,
            )
            for f in Path(app.config["GRAPHICS_PREVIEW_FOLDER"]).glob("*.html"):
                print(f"moving folder {f}")
                shutil.move(str(f), project_folder)

    # CALCULATE BLANKS
    control_file_1 = os.path.join(os.path.dirname(uploaded_excel_files[0]), "C1.txt")
    control_file_2 = os.path.join(os.path.dirname(uploaded_excel_files[0]), "C2.txt")
    ignore_loops = cache.get("ignored_loops")

    processed_files = []
    for idx, c in enumerate([control_file_1, control_file_2], start=1):
        C = ControlFile(
            flush,
            wait,
            close,
            c,
            file_type=f"control_{idx}",
            ignore_loops=ignore_loops,
        )
        C_Total = ResumeControl(C)
        C_Total.get_bank()
        processed_files.append(C)
    control = C_Total.calculate_blank()
    print(f"Valor 'Blanco' {control}")

    now = time.perf_counter()
    for data_file in uploaded_excel_files:
        experiment = ExperimentCycle(
            flush,
            wait,
            close,
            data_file,
            ignore_loops=ignore_loops,
            file_type="Experiment",
        )
        resume = ResumeDataFrame(experiment)
        resume.generate_resume(control)
        resume.save()
        processed_files.append(experiment)

    if plot:
        map(save_loop_graph, processed_files)
    if config["experiment_file_config"]["SAVE_LOOP_DF"]:
        map(save_loop_file, processed_files)
    if config["experiment_file_config"]["SAVE_CONVERTED"]:
        for f in processed_files:
            f.original_file.save(name=f"[Original]{f.original_file.fname}")

    TearDown(Path(experiment.original_file.folder_dst)).organize()
    cache.set("generating_files", False)
    print("✨ Tasca conclosa ✨")
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
        # IGNORED LOOPS
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
            f"""Els fitxers s'han carregat. Quan totes les dades s’hagin processat,
            estaran disponibles a la secció Descàrregues [{Path(project_folder).name}.zip].""",
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
    zip_folder = [str(p) for p in Path(app.config["ZIP_FOLDER"]).glob("*.zip")]
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
        for i, file_ in enumerate(zip_folder, start=1)
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
# API ROUTES
####################
@app.route("/status", methods=["GET"])
def get_status():
    """Return information about the different components of the system."""
    return jsonify({"generating_files": cache.get("generating_files")})


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
            if loops:
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
    # socketio.run(app, debug=False, host="0.0.0.0", port=port)
    socketio.run(app, debug=True, host="0.0.0.0", port=port)
