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
import json
import importlib
from runpy import run_path
from tendril.utils.versions import get_namespace_package_names
from tendril.utils.files import yml
from tendril.utils import log
logger = log.get_logger(__name__, log.DEFAULT)


class ConfigElement(object):
    def __init__(self, name, default, doc, parser=None):
        self.name = name
        self.default = default
        self.doc = doc
        self.parser = parser
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
    def raw_value(self):
        try:
            return self.ctx['_environment_overrides'][self.name]
        except KeyError:
            pass
        try:
            return self.ctx['_local_config'][self.name]
        except KeyError:
            pass

        try:
            return self.ctx['_instance_config'][self.name]
        except KeyError:
            pass

        try:
            if self.ctx['_external_configs']:
                return self.ctx['_external_configs'].get(self.name)
        except ExternalConfigKeyError:
            pass

        try:
            return eval(self.default, self.ctx)
        except SyntaxError:
            print("Required config option not set in "
                  "instance config : " + self.name)
            raise

    @property
    def value(self):
        if self.parser:
            return self.parser(self.raw_value)
        else:
            return self.raw_value


class ConfigOptionConstruct(ConfigElement):
    def __init__(self, name, parameters, doc):
        self._parameters = parameters
        super(ConfigOptionConstruct, self).__init__(name, None, doc)

    @property
    def value(self):
        raise NotImplementedError


class ExternalConfigMissingError(Exception):
    def __init__(self, source, filetype):
        self.source = source
        self.filetype = filetype


class ExternalConfigFormatError(Exception):
    def __init__(self, source, filetype):
        self.source = source
        self.filetype = filetype


class ExternalConfigKeyError(Exception):
    def __init__(self, source, key):
        self.source = source
        self.key = key


class ConfigSourceDoesNotProvideKey(ExternalConfigKeyError):
    pass


class ConfigSourceDoesNotContainKey(ExternalConfigKeyError):
    def __init__(self, source, key, key_path):
        super(ConfigSourceDoesNotContainKey, self).__init__(source, key)
        self.key_path = key_path


class ConfigSourceBase(object):
    def get(self, key):
        raise NotImplementedError


class ConfigExternalSource(ConfigSourceBase):
    def __init__(self, path, keymap):
        self._path = path
        self._keymap: dict = keymap

    @property
    def path(self):
        return self._path

    def get(self, key):
        if key not in self._keymap.keys():
            raise ConfigSourceDoesNotProvideKey(self._path, key)
        return self._get(self._keymap[key])

    def _get(self, key_path):
        raise NotImplementedError


class ConfigExternalJSONSource(ConfigExternalSource):
    def __init__(self, path, keymap):
        super(ConfigExternalJSONSource, self).__init__(path, keymap)
        self._source = None
        self._load_external_config()

    def _load_external_config(self):
        if not os.path.exists(os.path.expandvars(self._path)):
            raise ExternalConfigMissingError(self._path, 'json')
        with open(os.path.expandvars(self._path), 'r') as f:
            self._source = json.load(f)

    def _get(self, key_path):
        rval = self._source
        try:
            for crumb in key_path.split(':'):
                rval = rval.get(crumb)
        except KeyError:
            raise ConfigSourceDoesNotContainKey(self._source, None, key_path)
        return rval


class ConfigExternalSources(ConfigSourceBase):
    def __init__(self, path):
        super(ConfigExternalSources, self).__init__()
        self._path = path
        self._sources = []
        self._load_external_sources()

    def _load_external_sources(self):
        external_configs = yml.load(self._path)
        for config in external_configs:
            try:
                if config['format'] == 'json':
                    self._sources.append(
                        ConfigExternalJSONSource(config['path'], config['keymap'])
                    )
                else:
                    raise ExternalConfigFormatError(config['path'], config['filetype'])
            except ExternalConfigMissingError:
                pass

    def get(self, key):
        for source in self._sources:
            try:
                return source.get(key)
            except ExternalConfigKeyError:
                continue
        raise ExternalConfigKeyError(self._path, key)


class ConfigManager(object):
    def __init__(self, prefix, legacy, excluded):
        self._prefix = prefix
        self._excluded = excluded
        self._instance_config = None
        self._local_config = None
        self._external_configs: ConfigExternalSources = None
        self._environment_overrides = None
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

        try:
            self._environment_overrides = {}
            if self.ALLOW_ENVIRONMENT_OVERRIDES:
                if self.ENVIRONMENT_OVERRIDE_PREFIX:
                    for key, value in os.environ.items():
                        if key.startswith(self.ENVIRONMENT_OVERRIDE_PREFIX):
                            logger.info("Environment Config Override : {} : {}".format(key, value))
                            self._environment_overrides[key[len(self.ENVIRONMENT_OVERRIDE_PREFIX):]] = value
        except KeyError:
            pass

        if os.path.exists(self.EXTERNAL_CONFIG_SOURCES):
            logger.debug("Loading External Configuration Maps from {0}"
                         "".format(self.EXTERNAL_CONFIG_SOURCES))
            self._external_configs = ConfigExternalSources(self.EXTERNAL_CONFIG_SOURCES)

    @property
    def INSTANCE_CONFIG(self):
        return self._instance_config

    @property
    def LOCAL_CONFIG(self):
        return self._local_config

    @property
    def EXTERNAL_CONFIG(self):
        return self._external_configs

    @property
    def ENVIRONMENT_OVERRIDES(self):
        return self._environment_overrides

    def load_elements(self, elements, doc=''):
        """
        Loads the constants and/or options in the provided list into
        the config namespace.

        :param elements: `list` of :class:`ConfigConstant` or
                          :class:`ConfigOption` or
                          :class:`ConfigOptionConstruct`
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
