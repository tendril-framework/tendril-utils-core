# Copyright (C) 2015 Chintalagiri Shashank
#
# This file is part of Tendril.
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.
"""
The Log Utils Module (:mod:`tendril.utils.log`)
===============================================

This module provides utilities to deal with logging systems. The intent of
having this module instead of using :mod:`logging` directly is to allow the
injection of various default parameters and options into all the loggers
used from a central place, instead of littering them throughout the
modules.

At present, this module does nothing that is overly useful, except for
being able to set the default log level for all modules simultaneously.

.. rubric:: Usage Example

>>> from tendril.utils import log
>>> logger = log.get_logger(__name__, log.DEFAULT)

"""

import os
import sys
import logging
from loguru import logger


#: Level for debug entries. High volume is ok
from logging import DEBUG   # noqa
#: Level for informational entires. Low volume
from logging import INFO  # noqa
#: Warnings only, which inform of possible failure
from logging import WARNING  # noqa
#: Errors only, which inform of high likelihood of failure
from logging import ERROR  # noqa
#: Critical Errors, things which should halt execution entirely
from logging import CRITICAL  # noqa


#: The default log level for all loggers created through this module,
#: unless otherwise specified at the time of instantiation.
DEFAULT = logging.INFO


def apply_config(config=None):
    if not config:
        from tendril import config
    logging.root.setLevel(config.LOG_LEVEL)
    logger.configure(handlers=[{"sink": sys.stdout, "serialize": False}])
    create_log_file(config.LOG_PATH, config.JSON_LOGS)


def create_log_file(LOG_PATH, JSON_LOGS):
    logdir = os.path.split(LOG_PATH)[0]
    if not os.path.exists(logdir):
        os.makedirs(logdir)
    logger.add(LOG_PATH, level="INFO", serialize=JSON_LOGS, enqueue=True,
               rotation="1 week", retention="14 days", catch=True, backtrace=True)
    logging.info("Logging to: {}".format(LOG_PATH))


class InterceptHandler(logging.Handler):
    def emit(self, record):
        # Get corresponding Loguru level if it exists
        try:
            level = logger.level(record.levelname).name
        except ValueError:
            level = record.levelno

        # Find caller from where originated the logged message
        frame, depth = logging.currentframe(), 2
        while frame.f_code.co_filename == logging.__file__:
            frame = frame.f_back
            depth += 1

        logger.opt(depth=depth, exception=record.exc_info).log(level, record.getMessage())


def init():
    # intercept everything at the root logger
    logging.root.handlers = [InterceptHandler()]
    logging.root.setLevel(logging.INFO)

    # remove every other logger's handlers
    # and propagate to root logger
    for name in logging.root.manager.loggerDict.keys():
        logging.getLogger(name).handlers = []
        logging.getLogger(name).propagate = True

    # configure loguru
    logger.configure(handlers=[{"sink": sys.stdout, "serialize": False}])

    # logging.basicConfig(level=logging.DEBUG)
    silence = [
        logging.getLogger('watchdog.observers.inotify_buffer'),
        logging.getLogger('requests.packages.urllib3.connectionpool'),
        logging.getLogger('passlib.registry'),
        logging.getLogger('passlib.utils.compat'),
        logging.getLogger('appenlight_client.utils'),
        logging.getLogger('appenlight_client.timing'),
        logging.getLogger('appenlight_client.client'),
        logging.getLogger('appenlight_client.transports.requests'),
        logging.getLogger('pika.callback'),
        logging.getLogger('pika.channel'),
        logging.getLogger('pika.heartbeat'),
        logging.getLogger('pika.connection'),
        logging.getLogger('pika.adapters.base_connection'),
        logging.getLogger('pika.adapters.blocking_connection'),
        logging.getLogger('pika.adapters.select_connection'),
        logging.getLogger('urllib3.connectionpool'),
        logging.getLogger('matplotlib'),
        logging.getLogger('matplotlib.font_manager'),
        logging.getLogger('matplotlib.backends'),
        logging.getLogger('parso.python.diff'),
        logging.getLogger('parso.cache'),
    ]
    for external_logger in silence:
        external_logger.setLevel(logging.WARNING)
    logging.getLogger('pika.connection').setLevel(logging.ERROR)


def get_logger(name, level=None):
    """
    Get a logger with the specified ``name`` and an optional ``level``.

    The levels from the python :mod:`logging` module can be used directly.
    For convenience, these levels are imported into this module's namespace
    as well, along with the :data:`DEFAULT` level this module provides.

    See python :mod:`logging` documentation for information about log levels.

    :param name: The name of the logger
    :type name: str
    :param level: Log level of the logger to be used.
                  Default : :data:`DEFAULT`.
    :type level: int
    :return: The logger instance
    """
    built_logger = logging.getLogger(name)
    if level is not None:
        built_logger.setLevel(level)
    else:
        built_logger.setLevel(DEFAULT)
    return built_logger


getLogger = get_logger

init()
