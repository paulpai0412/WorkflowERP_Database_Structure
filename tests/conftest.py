import sys
import os
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def _install_windows_pytest_tmpdir_mode_fix() -> None:
    if os.name != "nt":
        return
    if getattr(Path.mkdir, "_wferp_pytest_tmpdir_mode_fix", False):
        return

    original_mkdir = Path.mkdir

    def mkdir_with_windows_safe_mode(self, mode=0o777, parents=False, exist_ok=False):
        if mode == 0o700:
            mode = 0o777
        return original_mkdir(self, mode=mode, parents=parents, exist_ok=exist_ok)

    mkdir_with_windows_safe_mode._wferp_pytest_tmpdir_mode_fix = True
    Path.mkdir = mkdir_with_windows_safe_mode


_install_windows_pytest_tmpdir_mode_fix()
