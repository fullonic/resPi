from pathlib import Path
import pytest
import requests
from selenium import webdriver
from selenium.common.exceptions import ElementNotInteractableException

# from core.utils import config_from_file, save_config_to_file

test_data = Path(".").resolve() / "tests/Data"
data_file = test_data / "angula.txt"
control_file_1 = test_data / "control1.txt"
control_file_2 = test_data / "control2.txt"


@pytest.fixture()
def driver():
    options = webdriver.FirefoxOptions()
    # options.add_argument("-Headless")
    # options.add_argument("-Headless")
    driver = webdriver.Firefox(options=options)
    return driver


# @pytest.mark.skip
def test_home_page(driver):
    driver.get("http://localhost:5000/")


def process_data_with_graphics(preview=False):
    driver = webdriver.Firefox()
    driver.get("http://localhost:5000/")
    control_file_1 = driver.find_element_by_id("control_file_1")
    control_file_2 = driver.find_element_by_id("control_file_2")
    data_file = driver.find_element_by_id("data_file")
    control_file_1.send_keys(str(test_data / "control1.txt"))
    control_file_2.send_keys(str(test_data / "control2.txt"))
    data_file.send_keys(str(test_data / "angula.txt"))
    submit = driver.find_element_by_id("submit_files")
    if not preview:
        submit.click()
    else:
        preview_plots(driver)


def preview_plots(driver):
    vista_previa = driver.find_element_by_id("generatePlotComplet")
    vista_previa.click()
    submit = driver.find_element_by_id("submit_files")
    submit.click()
    # Preview plots
    driver.implicitly_wait(10)
    driver.find_element_by_id("C1").send_keys("1,2")
    driver.find_element_by_id("C1ID").click()
    try:
        driver.find_element_by_id("myBtn").click()
    except ElementNotInteractableException:
        pass
    driver.find_element_by_xpath("/html/body/nav/a[2]").click()
    driver.implicitly_wait(0.5)
    driver.find_element_by_id("generatePlots").click()
    driver.find_element_by_id("submit_files").click()


def process_preview_and_plot():
    return process_data_with_graphics(True)


process_preview_and_plot()
