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
import logging
from runpy import run_path
from distutils.util import strtobool
from tendril.utils.versions import get_namespace_package_names
from tendril.utils.files import yml

logger = logging.getLogger(__name__)


def is_jsonable(x):
    try:
        json.dumps(x)
        return True
    except:
        return False


class ConfigElement(object):
    def __init__(self, name, default, doc, parser=None, masked=False):
        self.name = name
        self.default = default
        self.doc = doc
        self.parser = parser
        self.masked = masked
        self.source = None
        self.ctx = None

    def doc_render(self):
        return [self.name, self.doc, self.default,
                self.jsonable_value, self.source]

    @property
    def value(self):
        raise NotImplementedError

    @property
    def masked_value(self):
        """Return a masked version of the value of the option.

        If the option is not to be masked, the value is returned unchanged. 
        If the field is to be masked, the masked value is returned. The masking 
        algorithm is as follows:

        * If the value is not a string, it is returned unchanged.
        * If the value is a string, the first 8 characters (or 1/8 of the string, 
          whichever is shorter) are returned, followed by ellipses and the last 
          8 characters (or 1/8 of the string, whichever is shorter)

        (doc generated mostly by GitHub Copilot)
        Returns:
            str: The masked value of the field.
        """
        value = self.value
        if not self.masked:
            return value
        if not isinstance(value, str):
            return value

        v_len = len(value)
        m_len = int(min(v_len/8, 8))
        return f"{value[:m_len]}...{value[-m_len:]}"

    @property
    def jsonable_value(self):
        if is_jsonable(self.masked_value):
            return self.masked_value
        else:
            return str(self.masked_value)


def bool_parser(value):
    if not value:
        return False
    if isinstance(value, str):
        return strtobool(value)
    else:
        return bool(value)


class ConfigConstant(ConfigElement):
    """
    A configuration `constant`. This is fully specified in the core
    configuration module and cannot be changed by the user or the instance
    administrator without modifying the code.

    The value itself is constructed using ``eval()``.
    """
    @property
    def value(self):
        self.source = "hardcoded"
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
            rv = self.ctx['_environment_overrides'][self.name]
            self.source = 'environment_override'
            return rv
        except KeyError:
            pass

        try:
            rv = self.ctx['_local_config'][self.name]
            self.source = 'local_override'
            return rv
        except KeyError:
            pass

        try:
            rv = self.ctx['_instance_config'][self.name]
            self.source = 'instance_config'
            return rv
        except KeyError:
            pass

        try:
            if self.ctx['_external_configs']:
                rv = self.ctx['_external_configs'].get(self.name)
                self.source = 'external_config'
                return rv
        except ExternalConfigKeyError:
            pass

        try:
            rv = eval(self.default, self.ctx)
            self.source = 'default'
            return rv
        except SyntaxError:
            print("Required config option not set in "
                  "instance config : " + self.name)
            raise

    @property
    def value(self):
        """Get the value of the property.

        If a parser is defined, the value returned is the result of
        applying the parser to the raw value of the property. Otherwise,
        the raw value is returned.

        (doc generated mostly by GitHub Copilot)
        """
        if self.parser:
            if self.parser == bool:
                return bool_parser(self.raw_value)
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
        """
        This function loads the external config file into a dictionary

        The external config file is a json file that contains some
        configuration parameters for the application.

        (doc generated mostly by GitHub Copilot)
        """
        if not os.path.exists(os.path.expandvars(self._path)):
            raise ExternalConfigMissingError(self._path, 'json')
        with open(os.path.expandvars(self._path), 'r') as f:
            self._source = json.load(f)

    def _get(self, key_path):
        """Return the value at the end of the key_path.

        key_path is a string of the form 'key1:key2:key3' where each key
        is a key in a dict. This function will return the value of key3
        in the dict d[key1][key2]. If key1, key2, or key3 do not exist,
        a ConfigSourceDoesNotContainKey error will be raised.

        (doc generated mostly by GitHub Copilot)
        """
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
        """
        This method loads the external config files from the given path.
        It iterates over each config and determines the format of the file.
        If the format is JSON, it will create a ConfigExternalJSONSource object
        and add it to the list of sources. If the file format is not supported,
        it will raise an ExternalConfigFormatError.

        (doc generated mostly by GitHub Copilot)
        """
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
        """Return the value associated with the key in the configured 
        external sources.

        Returns the value associated with the key in the first source
        that has the key. If the key is not found in any of the sources,
        raise ExternalConfigKeyError.

        (doc generated mostly by GitHub Copilot)

        Args:
            key (str): The key to search for.

        Returns:
            The value associated with the key.

        Raises:
            ExternalConfigKeyError: If the key is not found in any of
                the sources.
        """
        for source in self._sources:
            try:
                return source.get(key)
            except ExternalConfigKeyError:
                continue
        raise ExternalConfigKeyError(self._path, key)


class ConfigManager(object):
    """The ConfigManager class provides a consistent interface for accessing
    configuration information from a variety of sources. It is intended to be
    a singleton.

    (doc generated mostly by GitHub Copilot)
    """
    def __init__(self, prefix, legacy, excluded, appname=None):
        self._prefix = prefix
        self._excluded = excluded
        self.APPNAME = appname

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
        """Load configuration elements from modules.

        This method will load configuration elements from modules in the 
        current namespace. It will respect the dependency order specified 
        in the depends attribute of each module while loading. If any 
        dependencies are not satisfied, the module will be skipped until 
        it is. If a module is skipped and there are no remaining modules
        to load, an error will be logged.

        (doc generated mostly by GitHub Copilot)
        """
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
        """ Loads the configuration from different sources to 
        populate the unified config object

        (doc generated mostly by GitHub Copilot)

        :return: None
        """
        if os.path.exists(self.INSTANCE_CONFIG_FILE):
            logger.info("Loading Instance Config from {0}"
                         "".format(self.INSTANCE_CONFIG_FILE))
            self._instance_config = run_path(self.INSTANCE_CONFIG_FILE)
        else:
            self._instance_config = {}

        if os.path.exists(self.LOCAL_CONFIG_FILE):
            logger.info("Loading Local Config from {0}"
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

    @property
    def docs(self):
        return self._docs

    def doc_render(self):
        """Returns a dictionary of documentation for the options.

        The dictionary is keyed by the names of the option groups. 
        The value for each group is a dictionary keyed by the names 
        of the options in that group. 
        
        Each option value is a dictionary with the keys:
        
        doc
            The documentation string for the option.

        default
            The default value for the option.

        value
            The value of the option after all configuration files have been
            read.

        source
            The filename of the configuration file from which the option was
            read, or None if the option was not read from a configuration
            file.

        (doc generated mostly by GitHub Copilot)

        """
        rv = {}
        for section, name in self._docs:
            items = {}
            for oname, doc, default, masked_value, source in section:
                items[oname] = {'doc': doc, 'default': default,
                                'value': masked_value, 'source': source}
            rv[name] = items
        return rv

    def json_render(self):
        """Render the config as a dict suitable for JSON encoding.

        The structure is as follows:

            {
                'section1': {
                    'item1': {
                        'value': 'value1',
                        'source': 'source1',
                    },
                    'item2': {
                        'value': 'value2',
                        'source': 'source2',
                    },
                },
                'section2': {
                    'item1': {
                        'value': 'value1',
                        'source': 'source1',
                    },
                    'item2': {
                        'value': 'value2',
                        'source': 'source2',
                    },
                },
            }

        (doc generated mostly by GitHub Copilot)

        :returns: a dict of the config.
        """
        rv = {}
        for section, name in self._docs:
            items = {}
            for oname, doc, default, masked_value, source in section:
                items[oname] = {'value': masked_value, 'source': source}
            rv[name] = items
        return rv

    def log_render(self):
        """This method logs the rendered configuration. It loops through
        the sections and names of the configuration, and prints the
        value of each option, as well as its source (the file in which
        it was defined). The value is masked if the option is sensitive.

        (doc generated mostly by GitHub Copilot)
        """
        for section, name in self._docs:
            logger.info('--------------------------------')
            logger.info(f"{name.upper()} : ")
            for oname, _, _, masked_value, source in section:
                logger.info("    {0:30} :  {1}     ({2})".format(oname, masked_value, source))


def generate_constants(instance_name):
    config_constants_basic = [
        ConfigConstant(
            'INSTANCE_NAME',
            "'{}'".format(instance_name),
            'Name of the instance. Used to determine configuration and resource paths.'
        ),
        ConfigConstant(
            'INSTANCE_ROOT_CANDIDATES',
            """list([
                    os.path.join(os.path.expanduser('~'), '.{}'.format(INSTANCE_NAME), 'tendril'),
                    os.path.join('/etc', INSTANCE_NAME, 'tendril'),
                    os.path.join(os.path.expanduser('~'), '.tendril'),
            ])""",
            'Paths to search for the INSTANCE_ROOT. First available path will be used.'
        ),
        ConfigConstant(
            'INSTANCE_ROOT',
            "list(filter(os.path.exists, INSTANCE_ROOT_CANDIDATES))[0]",
            "Path to the instance root. Can be redirected if necessary"
            "with a file named ``redirect`` in this folder."
        ),
    ]

    config_constants_environment = [
        ConfigConstant(
            'ALLOW_ENVIRONMENT_OVERRIDES',
            "True",
            'Whether config options can be overridden from the environment.'
        ),
        ConfigConstant(
            'ENVIRONMENT_OVERRIDE_PREFIX',
            "'{}_'.format(INSTANCE_NAME.upper())",
            'Environment variable name prefix.'
        ),
    ]

    config_constants_redirected = [
        ConfigConstant(
            'INSTANCE_CONFIG_FILE',
            "os.path.join(INSTANCE_ROOT, 'instance_config.py')",
            'Path to the tendril instance configuration.'
        ),
        ConfigConstant(
            'LOCAL_CONFIG_FILE',
            "os.path.join(INSTANCE_ROOT, 'local_config_overrides.py')",
            'Path to local overrides to the instance configuration.'
        ),
    ]

    config_constants_external = [
        ConfigConstant(
            'EXTERNAL_CONFIG_SOURCES',
            "os.path.join(INSTANCE_ROOT, 'external_configs.yaml')",
            "Path to a yaml definition file mapping to external config sources."
        )
    ]
    return config_constants_environment, config_constants_basic, config_constants_redirected, config_constants_external


def install_config(manager, instance_name):
    config_constants_environment, \
    config_constants_basic, \
    config_constants_redirected, \
    config_constants_external = generate_constants(instance_name)

    manager.load_elements(config_constants_basic,
                          doc="Tendril Default Instance Root")

    manager.load_elements(config_constants_environment,
                          doc="Environment Variable Override Configuration")

    logger.info("Using Instance Root {}".format(manager.INSTANCE_ROOT))

    if os.path.exists(os.path.join(manager.INSTANCE_ROOT, 'redirect')):
        logger.info("Found instance redirect")
        with open(os.path.join(manager.INSTANCE_ROOT, 'redirect'), 'r') as f:
            manager.INSTANCE_ROOT = f.read().strip()
            logger.info("Using Redirected Instance Root {}".format(manager.INSTANCE_ROOT))

    manager.load_elements(config_constants_redirected,
                          doc="Tendril Configuration Paths")

    manager.load_elements(config_constants_external,
                          doc="External Configuration Sources")

    manager.load_config_files()
    
