# (C) Datadog, Inc. 2018
# All rights reserved
# Licensed under a 3-clause BSD style license (see LICENSE)
import os

from stackstate_checks.dev import get_docker_hostname

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
TESTS_HELPER_DIR = os.path.join(ROOT, 'stackstate_checks_tests_helper')

CHECK_NAME = 'mysql'

HOST = get_docker_hostname()
PORT = 13306
SLAVE_PORT = 13307

USER = 'dog'
PASS = 'dog'
MARIA_ROOT_PASS = 'master_root_password'
