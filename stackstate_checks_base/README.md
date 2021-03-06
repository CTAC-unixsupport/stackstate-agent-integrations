# StackState Checks Base

## Overview

This package provides the Python bits needed by the [StackState Agent][1]
to run Agent-based Integrations (also known as _Checks_).

This _Check toolkit_ is used in two scenarios:

 1. When used from within the Python interpreter embedded in the Agent, it
 provides all the base classes and utilities needed by any Check.

 2. When installed in a local environment with a regular Python interpreter, it
 mocks the presence of a running Agent so checks can work in standalone mode,
 mostly useful for testing and development.

## Development

Create a dedicated virtualenv and follow the instructions in this paragraph
to work with the check.

To install the check in dev mode:
```
pip install -e ".[dev]"
```

To build the wheel package:
```
python setup.py bdist_wheel
```

To run the tests, [install tox][3] and just run:
```
tox
```

[1]: https://github.com/StackVista/stackstate-agent
[2]: https://github.com/StackVista/stackstate-agent-integrations
[3]: https://tox.readthedocs.io/en/latest/install.html
