echo Build app
echo -------------------------------------
pyinstaller --onedir --add-data 'templates:templates' --add-data 'static:static' --add-data 'logs:logs' --add-data "venv/lib/python3.8/site-packages/plotly:plotly" app.py
echo copying files
echo -------------------------------------
cp config.json dist/app/config.json
echo -------------------------------------
./dist/app/app
