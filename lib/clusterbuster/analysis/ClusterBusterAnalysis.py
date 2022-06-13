#!/usr/bin/env python3
# Copyright 2022 Robert Krawitz/Red Hat
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import sys
import importlib
import inspect


class ClusterBusterAnalyzeOne:
    def __init__(self, data: dict, metadata: dict):
        self._data = data
        self._metadata = metadata

    def Analyze(self):
        pass


class ClusterBusterAnalysis:
    """
    Analyze ClusterBuster reports
    """
    def __init__(self, data: dict):
        self._data = data

    def Analyze(self):
        report = dict()
        metadata = dict()
        if 'metadata' in self._data:
            metadata = self._data['metadata']
        for workload, workload_data in self._data.items():
            if workload == 'metadata':
                continue
            try:
                imported_lib = importlib.import_module(f'..{workload}_analysis', __name__)
            except Exception:
                print(f'Warning: no analyzer for workload {workload}', file=sys.stderr)
                return None
            try:
                for i in inspect.getmembers(imported_lib):
                    if i[0] == f'{workload}_analysis':
                        report[workload] = i[1](workload_data, metadata).Analyze()
            except Exception as exc:
                raise(exc)
        report['metadata'] = metadata
        return report
