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
import socket
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
_hostname = socket.gethostname()
_rename_modules = False
_names = {}
_source_maxlen = 15
identifier = ''

logger_levels = {}
loggers = {}


def _time_fmt(config):
    """
    Return a time format string for use with the log formatter.

    The returned string is used by the log formatter to format the time
    portion of the log message.

    The time format string is determined by the configuration options
    LOG_COMPACT_TS and LOG_COMPACT_TS_READABLE.

    LOG_COMPACT_TS is a boolean option that determines whether the log
    formatter should use a compact format for the time portion of the log
    message.

    LOG_COMPACT_TS_READABLE is a boolean option that determines whether the
    log formatter should use a human-readable format for the time portion of
    the log message when the compact format is selected.

    (doc generated mostly by GitHub Copilot)
    
    Args:
        config: A Config object.

    Returns:
        A format string for use with the log formatter.
    """
    if config.LOG_COMPACT_TS:
        if config.LOG_COMPACT_TS_READABLE:
            return '{time:%m-%d %H%M.%S}'
        return '{time:%s}'
    return '{time:YYYY-MM-DD HH:mm:ss.SSS}'


def _hostname_fmt(config):
    """Add hostname to message if LOG_INCLUDE_HOSTNAME is set.

    If LOG_HOSTNAME_PREFIX is set, remove it from the hostname.

    (doc generated mostly by GitHub Copilot)
    """
    if config.LOG_INCLUDE_HOSTNAME:
        if config.LOG_HOSTNAME_PREFIX:
            return f' | {_hostname.removeprefix(config.LOG_HOSTNAME_PREFIX)}'
        else:
            return f' | {_hostname}'
    return ''


def _level_fmt(config):
    """Return a format string that will be used to format the log level.
    The log level can be displayed as a compact string, a compact icon, or a
    full name.
    
    (doc generated mostly by GitHub Copilot)
    """
    if config.LOG_COMPACT_LEVEL:
        return '{level.name:^1.1}'
    if config.LOG_COMPACT_LEVEL_ICON:
        return '{level.icon:^1}'
    return '{level: <8}'


def _source_fmt(config):
    """Return a format string that will format the message source.
    
    (doc generated mostly by GitHub Copilot)"""
    if config.LOG_COMPACT_SOURCE:
        return '{extra[name]}'
    return '{name}'


def _config(config):
    """ If the config LOG_COMPACT_SOURCE set to True, then we 
    patch each record to include a shorter version of the module name. 
    This compacted string is set in the 'extra' dictionary of the 
    record and the 'name' field is not modified. This is done to avoid 
    any potential side effects within the logging system.
    
    (doc generated mostly by GitHub Copilot)
    """
    if config.LOG_COMPACT_SOURCE:
        global _rename_modules
        global _source_maxlen
        _rename_modules = True
        _source_maxlen = config.LOG_COMPACT_SOURCE_MAXLEN
        patcher = lambda r: _shortname(r['name'], r['extra'])
        return patcher
    return


def apply_config(config=None):
    if not config:
        from tendril import config
    global DEFAULT
    global identifier
    global logger_levels
    logger_levels = {k: logging.getLevelName(v) for k, v in config.LOG_LOGGER_LEVELS.items()}
    DEFAULT = config.LOG_LEVEL
    logging.root.setLevel(config.LOG_LEVEL)
    identifier = _hostname_fmt(config)

    configure_console_logs(config)
    create_log_file(config)


def _log_fmt(config):
    return "<green>" + _time_fmt(config) + identifier + "</green> | " \
          "<level>" + _level_fmt(config) + "</level> | " \
          "<cyan>" + _source_fmt(config) + "</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> " \
          "- <level><n>{message}</n></level>"


def create_log_file(config):
    logdir = os.path.split(config.LOG_PATH)[0]
    if not os.path.exists(logdir):
        os.makedirs(logdir)

    fmt = _log_fmt(config)
    logger.add(config.LOG_PATH, level="INFO", serialize=config.JSON_LOGS, enqueue=True,
               rotation="1 week", retention="14 days", format=fmt,
               catch=True, backtrace=True, diagnose=True)
    logging.info("Logging to: {}".format(config.LOG_PATH))


def configure_console_logs(config):
    patcher = _config(config)
    fmt = _log_fmt(config)
    params = {
        'handlers': [{"sink": sys.stdout, "serialize": False, "format": fmt,
                      'catch': True, 'backtrace': True, 'diagnose': True}],
    }
    if patcher:
        params['patcher'] = patcher
    logger.configure(**params)


class InterceptHandler(logging.Handler):
    loglevel_mapping = {
        50: 'CRITICAL',
        40: 'ERROR',
        30: 'WARNING',
        20: 'INFO',
        10: 'DEBUG',
        0: 'NOTSET',
    }

    def emit(self, record):
        # Get corresponding Loguru level if it exists
        try:
            level = logger.level(record.levelname).name
        except AttributeError:
            level = self.loglevel_mapping[record.levelno]
        except KeyError:
            level = record.levelno

        # Find caller from where originated the logged message
        frame, depth = sys._getframe(6), 6
        while frame and frame.f_code.co_filename == logging.__file__:
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

    # bootstrap loguru
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
        logging.getLogger('grafana_client.api')
    ]
    for external_logger in silence:
        external_logger.setLevel(logging.WARNING)
    logging.getLogger('pika.connection').setLevel(logging.ERROR)


def _shortname(name, extra):
    extra["name"] = _names.get(name, name)


_std_abbreviate = {'tendril': 't', 'libraries': 'lib'}
_never_abbreviate = ['db', 'config', 'mq']
_never_abbreviate_before = []
_never_abbreviate_after = []


def _tlen(parts):
    return sum([len(x) for x in parts]) + len(parts) - 1


def _recalculate_names():
    """This function is used to calculate the names of the
    modules that are used in the log messages. The names 
    thus calculated are stored in the _names dictionary and 
    used later via _shortname for each log message. This 
    dictionary contains the full name of the module as the 
    key, and the shortened name as the value.
    
    The shortened name is calculated by splitting the name 
    into a list of parts, and then abbreviating the parts 
    as needed using the tokens dictionary, which is 
    recalculated at every call to this function. 
    
    The parts are abbreviated if the length of the parts 
    list is greater than the maximum length, and if the 
    part is not in the list of parts that should never be 
    abbreviated.
    
    The parts of the name are abbreviated by abbreviating 
    the part to the shortest unique abbreviation.
    
    (doc generated mostly by GitHub Copilot)""" 
    global _names
    maxlen = _source_maxlen
    tokens = {}
    for name in _names.keys():
        parts = name.split('.')[:-1]
        for part in parts:
            current = tokens.get(part, {'abbrev': part, 'count': 0})
            current['count'] = current['count'] + 1
            tokens[part] = current
    for token in sorted(tokens.keys(), key=lambda x: tokens[x]['count'], reverse=True):
        if token in _std_abbreviate.keys():
            tokens[token]['abbrev'] = _std_abbreviate[token]
            done = True
        elif token in _never_abbreviate:
            tokens[token]['abbrev'] = token
            done = True
        else:
            done = False
        alen = 0
        while not done:
            alen = alen + 1
            abbrev = token[:alen]
            if abbrev not in [tokens[x]['abbrev'] for x in tokens.keys()]:
                tokens[token]['abbrev'] = abbrev
                done = True
    for name in _names.keys():
        parts = name.split('.')
        for idx, part in enumerate(parts[:-1]):
            if part in _never_abbreviate:
                continue
            try:
                if parts[idx + 1] in _never_abbreviate_before:
                    continue
            except IndexError:
                pass
            try:
                if parts[idx - 1] in _never_abbreviate_after:
                    continue
            except IndexError:
                pass
            if _tlen(parts) > maxlen:
                parts[idx] = tokens[part]['abbrev'] + '.'
            else:
                break
        _names[name] = '.'.join(parts)


def _register_name(name):
    global _names
    _names[name] = name
    if not _rename_modules:
        return
    _recalculate_names()


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
    global loggers
    if name in loggers.keys():
        return loggers[name]
    built_logger = logging.getLogger(name)
    if level is not None:
        built_logger.setLevel(level)
    elif name in logger_levels.keys():
        built_logger.setLevel(logger_levels[name])
    else:
        built_logger.setLevel(DEFAULT)
    if name not in _names.keys():
        _register_name(name)
    loggers[name] = built_logger
    return built_logger


def set_logger_level(name, level):
    if name not in loggers.keys():
        return
    if isinstance(level, str):
        level = logging.getLevelName(level)
    loggers[name].setLevel(level)


def known_loggers():
    return {k: v.level for k, v in loggers.items()}


getLogger = get_logger

init()
