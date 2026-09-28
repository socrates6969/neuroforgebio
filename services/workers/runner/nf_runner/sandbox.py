"""Process sandbox for local step execution (SEC-074, best effort) and the pinned step environment.

The subprocess runner starts every step as a fresh Python process with:

- an environment built from scratch (no inherited secrets such as database URLs or cloud keys):
  only the interpreter's needs, the thread pins of ``nf_steps.PINNED_ENV`` (determinism,
  BLUEPRINT §3.5) and the step-library search path;
- a private working/temp directory holding only the job's input and output directories;
- network disabled inside the interpreter: ``socket`` connect/bind/DNS raise before the step's code
  runs (:data:`BOOTSTRAP`);
- a wall-clock timeout and cancellation (the process is killed).

This is NOT an isolation boundary against hostile code (a step could reach the raw ``_socket``
module or the file system): it keeps honest steps honest and makes an accidental network call fail
loudly. The container runner is the real sandbox: ``--network none``, read-only root, non-root
user, no capabilities, CPU/memory/pids limits and only the job's input/output mounted.
"""

from __future__ import annotations

import os
import sys
from collections.abc import Iterable
from pathlib import Path

from nf_steps import PINNED_ENV

NETWORK_DISABLED = "network access is disabled in the step sandbox (SEC-074)"

# Executed with ``python -c`` before the step entrypoint. Keep it small and dependency-free.
BOOTSTRAP = (
    "import socket, sys, runpy\n"
    f"_MSG = {NETWORK_DISABLED!r}\n"
    "def _deny(*a, **k):\n"
    "    raise PermissionError(_MSG)\n"
    "for _n in ('connect', 'connect_ex', 'bind', 'sendto'):\n"
    "    setattr(socket.socket, _n, _deny)\n"
    "socket.create_connection = _deny\n"
    "socket.getaddrinfo = _deny\n"
    "socket.gethostbyname = _deny\n"
    "sys.argv = ['nf-step'] + sys.argv[1:]\n"
    "runpy.run_module('nf_steps', run_name='__main__', alter_sys=True)\n"
)

# Variables the interpreter itself needs on each platform (nothing application-specific).
_PASS_THROUGH = ("SYSTEMROOT", "WINDIR", "COMSPEC", "PATHEXT", "LANG", "LC_ALL")


def library_paths(extra_paths: Iterable[str | Path] = ()) -> list[str]:
    """``sys.path`` entries a step process needs: where nf_steps (and its deps) live + extras."""
    import nf_steps  # noqa: PLC0415

    paths = [str(Path(nf_steps.__file__).resolve().parents[1])]
    paths += [str(Path(p).resolve()) for p in extra_paths]
    return paths


def step_env(
    workdir: str | Path,
    *,
    extra_paths: Iterable[str | Path] = (),
    extra_libraries: Iterable[str] = (),
) -> dict[str, str]:
    """A minimal environment for one step process (built from scratch, not inherited)."""
    tmp = Path(workdir) / "tmp"
    tmp.mkdir(parents=True, exist_ok=True)
    env = {k: os.environ[k] for k in _PASS_THROUGH if k in os.environ}
    env.update(PINNED_ENV)
    env.update(
        {
            "PATH": str(Path(sys.executable).parent),
            "PYTHONPATH": os.pathsep.join(library_paths(extra_paths)),
            "PYTHONNOUSERSITE": "1",
            "PYTHONDONTWRITEBYTECODE": "1",
            "TMP": str(tmp),
            "TEMP": str(tmp),
            "TMPDIR": str(tmp),
            # a private, empty home (MNE and matplotlib resolve config paths from it)
            "HOME": str(tmp),
            "USERPROFILE": str(tmp),
            "MNE_DONTWRITE_HOME": "true",
            "MNE_HOME": str(tmp),
            "MPLCONFIGDIR": str(tmp),
            "NF_STEP_EXTRA_LIBRARIES": ",".join(extra_libraries),
        }
    )
    return env
