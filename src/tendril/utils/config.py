#!/usr/bin/env python
# encoding: utf-8

# Copyright (C) 2018 Chintalagiri Shashank
#
# This file is part of tendril.
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
Config Infrastructure Module (:mod:`tendril.utils.config`)
==========================================================

This module provides reusable infrastructure used by the tendril instance
configuration.

TODO Describe Architecture and Usage somewhere

"""

import os
import importlib
from runpy import run_path
from tendril.utils.versions import get_namespace_package_names
from tendril.utils import log
logger = log.get_logger(__name__, log.DEFAULT)


class ConfigElement(object):
    def __init__(self, name, default, doc):
        self.name = name
        self.default = default
        self.doc = doc
        self.ctx = None

    def doc_render(self):
        return [self.name, self.default, self.doc]


class ConfigConstant(ConfigElement):
    """
    A configuration `constant`. This is fully specified in the core
    configuration module and cannot be changed by the user or the instance
    administrator without modifying the code.

    The value itself is constructed using ``eval()``.
    """
    @property
    def value(self):
        return eval(self.default, self.ctx)


class ConfigOption(ConfigElement):
    """
    A configuration `option`. These options can be overridden
    by specifying them in the ``instance_config`` and
    ``local_config_overrides`` files.

    If specified in one of those files, the value should be
    the actual configuration value and not an expression. The
    default value specified here is used through ``eval()``.

    """
    @property
    def value(self):
        try:
            return self.ctx['_local_config'][self.name]
        except KeyError:
            pass
        try:
            return self.ctx['_instance_config'][self.name]
        except KeyError:
            try:
                return eval(self.default, self.ctx)
            except SyntaxError:
                print("Required config option not set in "
                      "instance config : " + self.name)
                raise


class ConfigManager(object):
    def __init__(self, prefix, legacy, excluded):
        self._prefix = prefix
        self._excluded = excluded
        self._instance_config = None
        self._local_config = None
        self._modules_loaded = []
        self._legacy = None
        self._docs = []
        self._load_legacy(legacy)
        self._load_configs()

    def _check_depends(self, depends):
        for m in depends:
            if m not in self._modules_loaded:
                return False
        return True

    def _load_legacy(self, m_name):
        if not m_name:
            return
        logger.debug("Loading legacy configuration from {0}".format(m_name))
        self._legacy = importlib.import_module(m_name)

    @property
    def legacy(self):
        return self._legacy

    def _load_configs(self):
        logger.debug("Loading configuration from {0}".format(self._prefix))
        modules = list(get_namespace_package_names(self._prefix))
        changed = True
        deadlocked = False
        while len(modules) and not deadlocked:
            if not changed:
                deadlocked = True
            changed = False
            remaining_modules = []
            for m_name in modules:
                if m_name in self._excluded:
                    continue
                m = importlib.import_module(m_name)
                if self._check_depends(m.depends):
                    logger.debug("Loading {0}".format(m_name))
                    m.load(self)
                    self._modules_loaded.append(m_name)
                    changed = True
                else:
                    if deadlocked:
                        logger.error("Failed loading {0}. Missing dependency."
                                     "".format(m_name))
                    remaining_modules.append(m_name)
            modules = remaining_modules

    def load_config_files(self):
        if os.path.exists(self.INSTANCE_CONFIG_FILE):
            logger.debug("Loading Instance Config from {0}"
                         "".format(self.INSTANCE_CONFIG_FILE))
            self._instance_config = run_path(self.INSTANCE_CONFIG_FILE)
        else:
            self._instance_config = {}
        if os.path.exists(self.LOCAL_CONFIG_FILE):
            logger.debug("Loading Local Config from {0}"
                         "".format(self.LOCAL_CONFIG_FILE))
            self._local_config = run_path(self.LOCAL_CONFIG_FILE)
        else:
            self._local_config = {}

    @property
    def INSTANCE_CONFIG(self):
        return self._instance_config

    @property
    def LOCAL_CONFIG(self):
        return self._local_config

    def load_elements(self, elements, doc=''):
        """
        Loads the constants and/or options in the provided list into
        the config namespace.

        :param elements: `list` of :class:`ConfigConstant` or
                          :class:`ConfigOption`
        :return: None
        """
        _doc_part = []
        for element in elements:
            element.ctx = self.__dict__
            element.ctx['os'] = os
            setattr(self, element.name, element.value)
            _doc_part.append(element.doc_render())
        self._docs.append([_doc_part, doc])

    def instance_path(self, path):
        return os.path.join(self.INSTANCE_ROOT, path)

    def doc_render(self):
        return self._docs
