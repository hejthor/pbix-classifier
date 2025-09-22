@echo off

echo [COMMAND PROMPT] Activating virtual environment
python -m venv venv
call venv\Scripts\activate

echo [COMMAND PROMPT] Upgrading pip to avoid warnings
pip install --upgrade pip

echo [COMMAND PROMPT] Installing Python dependencies
pip install -r resources\requirements.txt

echo [COMMAND PROMPT] Running app.py with classification
python resources\app.py --parameters input\parameters.json

echo [COMMAND PROMPT] Deactivating virtual environment
deactivate