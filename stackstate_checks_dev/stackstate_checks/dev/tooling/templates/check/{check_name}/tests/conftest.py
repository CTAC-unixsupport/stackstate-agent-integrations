{license_header}import pytest


@pytest.fixture(scope='session')
def sts_environment():
    # This conf instance is used when running `checksdev env start mycheck myenv`. 
    # The start command places this as a `conf.yaml` in the `conf.d/mycheck/` directory.
    # If you want to run an environment this object can not be empty. 
    return {{ "key": "value" }}

@pytest.fixture
def instance():
    return {{}}
