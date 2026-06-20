@echo off
chcp 65001 >nul
set "PYTHONUTF8=1"
set "PYTHONIOENCODING=utf-8"
set "TOOL_BIN=%~dp0bin"
set "CODEX_PYTHON=C:\Users\ivychi\.cache\codex-runtimes\codex-primary-runtime\dependencies\python"
set "NODE_HOME=C:\Users\ivychi\util\nodejs"
set "PATH=%TOOL_BIN%;%CODEX_PYTHON%;%NODE_HOME%;%PATH%"
echo WFERP local tools are active for this cmd session.
