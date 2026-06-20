@echo off
set "CODEX_PYTHON=C:\Users\ivychi\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe"
if exist "%CODEX_PYTHON%" (
  "%CODEX_PYTHON%" -m pytest %*
) else (
  py -3 -m pytest %*
)
