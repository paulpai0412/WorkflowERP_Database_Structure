@echo off
set "CODEX_PYTHON=C:\Users\ivychi\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe"
if exist "%CODEX_PYTHON%" (
  "%CODEX_PYTHON%" %*
) else (
  py -3 %*
)
