import tkinter as tk

from pathlib import Path
import urllib
import shutil


def download():
    """Download and "install" last version of resPi desktop app."""
    # Get user documents folder
    docs_folder = Path().home() / "Documents"
    # Get user Desktop folder
    desktop_folder = Path().home() / "Desktop"
    # Download zip file
    zip_url = "https://github.com/fullonic/flask_uploads/archive/master.zip"
    zip_file = docs_folder / "app.zip"
    try:
        print("Downloading the application into your documents folder")
        urllib.request.urlretrieve(zip_url, zip_file)
        # Send zip file into documents folder and unzip
        shutil.unpack_archive(zip_file, docs_folder)
    except FileExistsError:
        # We can handle here updates instead of a new installation to avoid data loose
        pass
    # Create app shortcut and move it to the desktop
    app_exc = docs_folder / "flask_uploads-master/setup.py"
    print("Creating app shortcut into your desktop")
    desktop_shortcut = desktop_folder / "app.py"
    Path(desktop_shortcut).symlink_to(app_exc, target_is_directory=True)
    # Delete zip folder
    Path(zip_file).unlink()
    print("You can now user resPi - Desktop File Processing")
    print("Any issues visit www.dbfsoft.net")


# GUI
window = tk.Tk()
window.title("resPi")
window.rowconfigure(0, minsize=50, weight=1)
window.columnconfigure(1, minsize=50, weight=1)
tk.Text(window)
welcome_label = tk.Label(text="Welcome resPi downloader and installer for windows")
fr_buttons = tk.Frame(window, relief=tk.RAISED, bd=2)
btn_download = tk.Button(fr_buttons, text="Download and install", command=download)

desktop_icons = tk.BooleanVar()


welcome_label.grid(row=0, column=0, sticky="ew")
btn_download.grid(row=1, column=0, sticky="ew",)

fr_buttons.grid(row=1, column=0, sticky="ns")
# btn_checkbox = tk.Checkbutton(window, text="Create desktop icon?").grid(row=1, column=1)

window.mainloop()
