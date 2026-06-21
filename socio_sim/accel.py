"""Optional GPU acceleration: run array kernels on CuPy when a GPU + CuPy are
present, else NumPy. The NumPy path is the verified default (CI has no GPU); the
CuPy path executes the identical array ops on-device. Honest scope: the GPU path
is enabled automatically when available but is NOT exercised in CI without a
device — treat it as opt-in/unverified-on-hardware-here.
"""

from __future__ import annotations


def array_module():
    """Return cupy if an actual GPU device is usable, else numpy."""
    try:
        import cupy as cp
        cp.zeros(1)  # touch a device; raises if none usable
        return cp
    except Exception:
        import numpy as np
        return np


def using_gpu() -> bool:
    return array_module().__name__ == "cupy"


def to_numpy(a):
    """Bring an array back to host numpy (no-op for numpy; .get() for cupy)."""
    if type(a).__module__.split(".")[0] == "cupy":
        import cupy as cp
        return cp.asnumpy(a)
    return a
