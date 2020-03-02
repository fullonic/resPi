import re
import filecmp

from pathlib import Path
from time import sleep

import pytest
import requests

URL = "http://localhost:5000"

test_data = Path(__file__).parent / "Data"
data_file = test_data / "angula.txt"
control_file_1 = test_data / "control1.txt"
control_file_2 = test_data / "control2.txt"
FILES = dict(
    data_file=(open(data_file, "rb")),
    control_file_1=(open(control_file_1, "rb")),
    control_file_2=(open(control_file_2, "rb")),
)

ROOT_DIR = Path(__file__).parent.parent


@pytest.mark.skip
def test_preview_global_plots():
    """Global plots.
    WHEN: User upload and wants see the vista previa
    """
    data = dict(
        flush=3,
        wait=10,
        close=40,
        experiment_plot=True,
        # plot=False,
        data_ignore_loops="2",
        c1_ignore_loops="1",
        c2_ignore_loops="2",
    )
    response = requests.post(f"{URL}/excel_files", data=data, files=FILES)

    templates_folder = ROOT_DIR / "templates/previews"
    assert response.status_code == 200
    for f in templates_folder.glob("*.html"):
        assert f.name in ["C1.html", "Experiment.html", "C2.html"]
        f.unlink()


@pytest.mark.skip
def test_file_upload_and_graphic():
    """Global plots.
    WHEN: User upload and wants tables plus graphics
    """
    data = dict(
        flush=3,
        wait=10,
        close=40,
        # experiment_plot=True,
        plot=False,
        data_ignore_loops="2",
        c1_ignore_loops="1",
        c2_ignore_loops="2",
    )
    response = requests.post(f"{URL}/excel_files", data=data, files=FILES)

    templates_folder = ROOT_DIR / "templates/previews"
    assert response.status_code == 200
    for f in templates_folder.glob("*.html"):
        assert f.name in ["C1.html", "Experiment.html", "C2.html"]
        # f.unlink()


@pytest.mark.skip
def test_zip_file_exist():
    """Test zipped file exist.

    WHEN: User upload
    THEN: Wants download zip file
    """
    data = dict(
        flush=3,
        wait=10,
        close=40,
        data_ignore_loops="",
        c1_ignore_loops="",
        c2_ignore_loops="",
    )
    response = requests.post(f"{URL}/excel_files", data=data, files=FILES)
    zip_folder = ROOT_DIR / "static/uploads/zip_files"
    assert response.status_code == 200
    # Get the file name from flash message
    pattern = r"\w+\.zip"
    fname = re.search(pattern, response.text)
    assert fname.group() is not None
    if fname.group():
        zip = zip_folder / fname.group()
        while not zip.exists():
            sleep(0.5)
        assert zip.exists() is True
        zip.unlink()


@pytest.mark.skip
def test_file_upload_graphic():
    # Upload and generate preview
    data = dict(
        flush=3,
        wait=10,
        close=40,
        experiment_plot=True,
        data_ignore_loops="",
        c1_ignore_loops="",
        c2_ignore_loops="",
    )
    response = requests.post(f"{URL}/excel_files", data=data, files=FILES)
    pattern = r"\w+\.zip"
    fname = re.search(pattern, response.text)
    project_folder = fname.group().split(".")[0]
    preview_txt_files = [
        str(f) for f in (ROOT_DIR / "static/uploads/preview").glob("*.txt")
    ]
    sorted(preview_txt_files)

    # Upload and generate all graphics
    uploaded_files = [
        str(f)
        for f in (ROOT_DIR / f"static/uploads/angula_24_02_2020_18_24_06").glob("*.txt")
    ]
    sorted(uploaded_files)
    for preview, uploaded in zip(uploaded_files, preview_txt_files):
        if not filecmp.cmp(preview, uploaded):
            continue
        else:
            # move html file from templates preview into project folder
            # add flag to cache that global plot of this file already exist
            # {fname_gplot: True}
            pass


@pytest.mark.skip
def test_main_page():
    response = requests.get(URL)
    assert response.status_code == 200
    print("ok")


# @pytest.mark.skip
def test_file_upload_simple():
    """Test basic upload.
    WHEN: User upload and only wants tables data
    THEN: Process only the data
    """
    data = dict(
        flush=3,
        wait=10,
        close=40,
        data_ignore_loops="2",
        c1_ignore_loops="1",
        c2_ignore_loops="2",
    )
    response = requests.post(f"{URL}/excel_files", data=data, files=FILES)
    assert response.status_code == 200
    # Get the file name from flash message
    pattern = r"\w+\.zip"
    resp = re.search(pattern, response.text)
    assert resp.group() is not None
