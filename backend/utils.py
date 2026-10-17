import pathlib
import typing
import builtins

# Wrapper to safely open files and strip unexpected arguments like metadata_errors
def open_safe(path: str | pathlib.Path, mode: str = "r", buffering: int = -1, encoding: str | None = None, errors: str | None = None, newline: str | None = None, closefd: bool = True, opener: typing.Callable[[str, str], typing.IO] | None = None, **kwargs) -> typing.IO:
    """Safe file open wrapper that removes unsupported keyword arguments.
    
    This prevents errors like "open() got an unexpected keyword argument 'metadata_errors'"
    when code accidentally passes arguments meant for other functions (e.g., av.open).
    """
    # Explicitly allowed kwargs for built-in open()
    allowed_kwargs = {
        "buffering",
        "encoding",
        "errors",
        "newline",
        "closefd",
        "opener",
    }
    # Build final arguments dictionary with only allowed kwargs
    args_dict = {"file": path, "mode": mode}
    for k, v in kwargs.items():
        if k in allowed_kwargs:
            args_dict[k] = v
    return builtins.open(**args_dict)

# Alias for backward compatibility
def open_wrapper(*args, **kwargs):
    return open_safe(*args, **kwargs)
