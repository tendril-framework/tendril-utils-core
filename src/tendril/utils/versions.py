#!/usr/bin/env python
# encoding: utf-8

# Copyright (C) 2016-2019 Chintalagiri Shashank
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
Collation Package Versions Module (:mod:`tendril.utils.versions`)
=================================================================

This module provides reusable infrastructure used for managing the landscape
and version information of the tendril namespace package collation.

TODO Describe Architecture and Usage somewhere

"""


from __future__ import print_function

import os
import pkg_resources
import pkgutil
import importlib


def get_namespace_package_names(namespace):
    ns_module = importlib.import_module(namespace)
    for _, name, _ in pkgutil.iter_modules(ns_module.__path__,
                                           ns_module.__name__ + '.'):
        yield name


def _namespace_primary_location(namespace, fpath):
    while os.path.split(fpath)[1] != namespace.split('.')[-1]:
        fpath = os.path.split(fpath)[0]
    return fpath


def get_namespace_package_locations(namespace):
    ns_package_names = get_namespace_package_names(namespace)
    ns_package_files = [pkgutil.get_loader(name).get_filename()
                        for name in ns_package_names]
    ns_package_locations = set([_namespace_primary_location(namespace, f)
                               for f in ns_package_files])
    return ns_package_locations


def get_version(package):
    try:
        return pkg_resources.get_distribution(package).version
    except pkg_resources.DistributionNotFound:
        return 'Not Installed'


def get_versions(prefix):
    return sorted([(d.project_name, d.version)
                   for d in pkg_resources.working_set
                   if d.project_name.startswith(prefix)],
                  key=lambda x: x[0])


class FeatureUnavailable(Exception):
    def __init__(self, feature=None, provider=None):
        self._feature = feature
        self._provider = provider

    def __repr__(self):
        return "<FeatureUnavailable {0}>\nThis feature might be provided by " \
               "{1}.".format(self._feature, self._provider)


def main():
    print(' {0:34} : {1}'.format('Tendril Version',
                                 get_version('tendril-framework')))
    print(' Installed Components : ')
    for package, version in get_versions('tendril'):
        print('   {0:32} : {1}'.format(package, version))


if __name__ == '__main__':
    main()
