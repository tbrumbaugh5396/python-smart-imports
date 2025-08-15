# smart_import.py
import sys
from pathlib import Path
import importlib

def smart_import(module_path: str, package_root: str = None):
    """
    Dynamically imports a module using an absolute import path.
    Ensures the import works whether the file is run directly or as part of a package.
    
    Args:
        module_path (str): Dotted path to the module (e.g., 'myproject.utils.helpers')
        package_root (str): Optional. Path to the package root (if not auto-detectable)

    Returns:
        module: The imported module object
    """
    # Get caller's frame to determine if running as script
    caller_frame = sys._getframe(1)
    caller_globals = caller_frame.f_globals
    
    # Check if the caller is running as a script
    if (caller_globals.get("__name__") == "__main__" and 
        caller_globals.get("__package__") is None):
        # Running as a script, patch sys.path
        if package_root is None:
            # Default: assume package root is one directory up from caller file
            caller_file = Path(caller_globals["__file__"])
            package_root = str(caller_file.resolve().parent.parent)
        
        if package_root not in sys.path:
            sys.path.insert(0, package_root)

    return importlib.import_module(module_path)
