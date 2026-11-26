@echo off
REM Sequentially run the three scripts from this folder.
setlocal

REM Move to the desired working directory.
cd /d "D:\store"

echo [%time%] Running 1_db_query.py...
python -u 1_db_query.py
if errorlevel 1 goto :end

echo [%time%] Running 2_brench.py...
python -u 2_brench.py
if errorlevel 1 goto :end

echo [%time%] Running 3_store.py...
python -u 3_store.py

:end
echo [%time%] Done.
endlocal
