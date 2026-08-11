"""Restricted unpickler for loading sklearn model files safely.

Prevents arbitrary code execution via malicious .pkl files. Only allows
sklearn, numpy, scipy, and a small set of built-in types — the constrained
set needed for sklearn estimator deserialization.
"""
import pickle
import io


class RestrictedUnpickler(pickle.Unpickler):
    """Unpickler that whitelists allowed modules/classes.

    Defense-in-depth against pickle deserialization attacks. The model files
    are server-trained and path-traversal is already guarded, but this adds
    a final safety net: if an attacker ever gains write access to the model
    directory, a crafted .pkl cannot execute arbitrary code.
    """

    # Allowed module prefixes for sklearn/numpy/scipy model objects.
    # Note: bare names ("numpy", "scipy") are included because numpy/scipy
    # pickle globals sometimes use the top-level module name with the class
    # as the symbol (e.g. "numpy" + "ndarray", "numpy" + "dtype",
    # "numpy.core.multiarray" + "_reconstruct").
    # Security: "builtins" is NOT a prefix — it is matched name-by-name via
    # _ALLOWED_NAMES so dangerous builtins (eval/exec/open/compile/...) can
    # never pass the module-prefix rule (previously any builtins.* global was
    # allowed, defeating the no-arbitrary-code-execution guarantee).
    _ALLOWED_PREFIXES = (
        "sklearn.",
        "numpy.",
        "numpy",
        "scipy.",
        "scipy",
        "collections",
    )

    # Specific allowed built-in names (checked BEFORE the prefix rule).
    _ALLOWED_NAMES = frozenset({
        "list", "dict", "tuple", "set", "frozenset",
        "complex", "float", "int", "str", "bytes", "bool",
        "numpy", "scipy", "sklearn",
    })

    def find_class(self, module, name):
        # Builtins are name-allowlisted only — never by prefix. This closes
        # the RCE gap where a crafted .pkl referenced builtins.eval/exec/open.
        if module == "builtins":
            if name in self._ALLOWED_NAMES:
                return super().find_class(module, name)
            raise pickle.UnpicklingError(
                f"RestrictedUnpickler: forbidden built-in '{name}' — "
                f"only data containers are allowed"
            )
        # Allow by module prefix (sklearn.*, numpy.*, scipy.*).
        if any(module.startswith(prefix) for prefix in self._ALLOWED_PREFIXES):
            return super().find_class(module, name)
        raise pickle.UnpicklingError(
            f"RestrictedUnpickler: forbidden class '{module}.{name}' — "
            f"only sklearn/numpy/scipy/builtins are allowed"
        )


def restricted_load(file_obj):
    """Load a pickle from a file object using RestrictedUnpickler."""
    return RestrictedUnpickler(file_obj).load()


def restricted_loads(data: bytes):
    """Load a pickle from bytes using RestrictedUnpickler."""
    return RestrictedUnpickler(io.BytesIO(data)).load()
