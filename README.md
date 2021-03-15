This application was design to run in a windows system by non programmer person. Therefore, an _installer_ was made using [pyinstaller](https://pyinstaller.readthedocs.io/en/stable/)

`pyinstaller` hooks to compile flask app:
* https://github.com/ciscomonkey/flask-pyinstaller
* https://github.com/miguelgrinberg/python-socketio/issues/35  # If flask-SocketIO is part of the app

To compile statsmodels package:
* https://github.com/pyinstaller/pyinstaller/issues/3921
* https://github.com/pyinstaller/pyinstaller/issues/2183

Fix issues with plotly by copying all plotly package into pyi folder.
See: https://stackoverflow.com/questions/46099695/pyinstaller-fails-with-plotly


`pyinstaller` command on linux based system:
```shell
>> pyinstaller --onedir --icon=icon.ico --add-data 'templates:templates' --add-data 'static:static' --add-data 'logs:logs' --add-data "config.json:." --add-data "venv/lib/python3.8/site-packages/plotly:plotly" app.py
```
Note: On windows platform, replace `:` by `;` and set the plotly path to `venv\Lib\site-packages\plotly;plotly`. Full command:
```shell
>>pyinstaller --onedir --icon=icon.ico --add-data 'templates;templates' --add-data 'static;static' --add-data 'logs;logs' --add-data "config.json;." --add-data "venv\Lib\site-packages\plotly;plotly":plotly" app.py
```
Full command including all hooks:
```shell
>> pyinstaller --onefile --add-data 'templates:templates' --add-data 'static:static' --add-data 'logs:logs' --add-data "venv/lib/python3.8/site-packages/plotly:plotly" app.py --hidden-import=statsmodels.tsa.statespace._kalman_filter --hidden-import=statsmodels.tsa.statespace._kalman_smoother --hidden-import=statsmodels.tsa.statespace._representation --hidden-import=statsmodels.tsa.statespace._simulation_smoother --hidden-import=statsmodels.tsa.statespace._statespace --hidden-import=statsmodels.tsa.statespace._tools --hidden-import=statsmodels.tsa.statespace._filters._conventional --hidden-import=statsmodels.tsa.statespace._filters._inversions --hidden-import=statsmodels.tsa.statespace._filters._univariate --hidden-import=statsmodels.tsa.statespace._smoothers._alternative --hidden-import=statsmodels.tsa.statespace._smoothers._classical --hidden-import=statsmodels.tsa.statespace._smoothers._conventional --hidden-import=statsmodels.tsa.statespace._smoothers._univariate
```
