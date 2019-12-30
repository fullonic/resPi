import pytest

from app import app as app_

data_file = "/home/somnium/Desktop/fake_cycle.txt"
control_file_1 = "/home/somnium/Desktop/control_1.txt"
control_file_2 = "/home/somnium/Desktop/control_2.txt"


@pytest.fixture()
def client():
    app = app_
    app.config["DEBUG"] = True

    testing_client = app.test_client()

    ctx = app.app_context()
    ctx.push()
    yield testing_client
    ctx.pop()


def test_upload_excel_files(client):
    data = {
        "control_file_1": (open(control_file_1, "rb"), control_file_1),
        "data_file": (open(data_file, "rb"), data_file),
        "control_file_2": (open(control_file_2, "rb"), control_file_2),
        "flush": 2,
        "wait": 2,
        "close": 20,
    }
    response = client.post(
        "/excel_files",
        data=data,
        content_type="multipart/form-data",
        # follow_redirects=True,
    )
    print(f"{response=}")
