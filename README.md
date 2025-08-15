# Smart Import

A Python utility for intelligent module imports that works whether files are run directly or as part of a package.

## Overview

Smart Import solves the common problem of Python modules that fail to import when run as scripts versus when imported as part of a package. It provides a simple function that dynamically adjusts the import path to ensure modules can be imported consistently in both contexts.

## Features

- **Dynamic import resolution**: Automatically handles both script and package execution contexts
- **Zero dependencies**: Uses only Python standard library modules
- **Simple API**: Just one function to replace problematic imports
- **Cross-platform**: Works on Windows, macOS, and Linux
- **Python 3.8+**: Compatible with modern Python versions

## Installation

### From PyPI (when published)
```bash
pip install smart-import
```

### From Source
```bash
git clone https://github.com/your-username/smart-import.git
cd smart-import
pip install -e .
```

## Usage

### Basic Usage

Replace problematic imports with `smart_import()`:

```python
# Instead of this (which might fail):
# from myproject.utils.helpers import some_function

# Use this:
from smart_import import smart_import
helpers = smart_import('myproject.utils.helpers')
some_function = helpers.some_function
```

### With Custom Package Root

If auto-detection doesn't work, specify the package root manually:

```python
from smart_import import smart_import
module = smart_import('myproject.utils.helpers', package_root='/path/to/project')
```

## How It Works

Safe Import uses Python's introspection capabilities to:

1. **Detect execution context**: Checks if the calling file is being run as a script (`__name__ == "__main__"` and `__package__ is None`)
2. **Auto-locate package root**: By default, assumes the package root is one directory up from the calling file
3. **Adjust sys.path**: Temporarily adds the package root to Python's module search path
4. **Import normally**: Uses `importlib.import_module()` with the corrected path

## Common Use Cases

### Project Structure
```
myproject/
├── main.py                 # Entry point script
├── myproject/
│   ├── __init__.py
│   ├── core/
│   │   ├── __init__.py
│   │   └── engine.py
│   └── utils/
│       ├── __init__.py
│       └── helpers.py
└── tests/
    └── test_helpers.py
```

### Running as Script
When `main.py` is run directly, imports from `myproject.utils` would normally fail. Safe Import resolves this:

```python
# main.py
from smart_import import smart_import

# This works whether main.py is run directly or imported
helpers = smart_import('myproject.utils.helpers')
engine = smart_import('myproject.core.engine')
```

### In Test Files
Perfect for test files that need to import modules from the main package:

```python
# tests/test_helpers.py
from smart_import import smart_import

# Works regardless of how tests are run
helpers = smart_import('myproject.utils.helpers')

def test_helper_function():
    assert helpers.some_function() == expected_result
```

### Using the Example Script
The `examples/smart_import_helper.py` script demonstrates how to use smart_import:

```bash
python examples/smart_import_helper.py
```

## API Reference

### `smart_import(module_path, package_root=None)`

Dynamically imports a module using an absolute import path.

**Parameters:**
- `module_path` (str): Dotted path to the module (e.g., 'myproject.utils.helpers')
- `package_root` (str, optional): Path to the package root directory. If not provided, auto-detects by assuming it's one directory up from the calling file.

**Returns:**
- `module`: The imported module object

**Raises:**
- `ImportError`: If the module cannot be found or imported

## Development

### Setting Up Development Environment

```bash
git clone https://github.com/your-username/smart-import.git
cd smart-import
pip install -e ".[dev]"
```

### Running Tests

```bash
pytest tests/
```

### Code Formatting

```bash
black src/
flake8 src/
mypy src/
```

### Building Distribution

```bash
python -m build
```

## Scripts

The `scripts/` directory contains utility scripts:

- `create_app_bundle.py`: Creates macOS application bundle
- `create_icon.py`: Generates application icons
- `create_requirements.txt`: Generates requirements.txt from current environment
- `create_requirements_dev.txt`: Generates development requirements

## Contributing

1. Fork the repository
2. Create a feature branch: `git checkout -b feature-name`
3. Make your changes and add tests
4. Run the test suite: `pytest`
5. Commit your changes: `git commit -am 'Add some feature'`
6. Push to the branch: `git push origin feature-name`
7. Submit a pull request

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## Changelog

### Version 1.0.0
- Initial release
- Basic safe import functionality
- Command line interface
- Cross-platform support

## Troubleshooting

### Common Issues

**Import still fails after using smart_import:**
- Check that the `module_path` is correct
- Verify the `package_root` points to the correct directory
- Ensure all parent directories have `__init__.py` files

**Auto-detection of package root doesn't work:**
- Manually specify the `package_root` parameter
- Check your project structure matches expected layout

**Module found but attributes missing:**
- Ensure the module is properly initialized
- Check for circular imports in your modules

### Getting Help

- Check the [Issues](https://github.com/your-username/smart-import/issues) page
- Create a new issue with a minimal reproduction case
- Include your Python version and operating system

## Related Projects

- [importlib](https://docs.python.org/3/library/importlib.html) - Python's standard import machinery
- [pathlib](https://docs.python.org/3/library/pathlib.html) - Object-oriented filesystem paths
