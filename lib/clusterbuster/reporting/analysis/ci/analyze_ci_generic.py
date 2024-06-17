#!/usr/bin/env python3
# Copyright 2023 Robert Krawitz/Red Hat
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

from ..ClusterBusterAnalysis import ClusterBusterAnalyzeOneBase


class CIAnalysis(ClusterBusterAnalyzeOneBase):
    """
    Analyze files data
    """

    def __init__(self, workload: str, data: dict, metadata: dict, variables: list):
        super().__init__(workload, data, metadata)
        self._variables = variables

    def _analyze_recurse(self, variables: list, desc: str, data: dict, answer: dict = {}):
        var = variables[0]
        if 'test_description' not in answer:
            answer['test_description'] = {'workload': self._workload}
        for key, value in data.items():
            answer['test_description'][var] = key
            if len(variables) == 1:
                subanswer = {
                    'uuid': self._metadata['jobs'][key]['uuid'],
                    'test_description': {'name': desc}
                    }
                for name, val in answer['test_description'].items():
                    subanswer['test_description'][name] = val
                for name, item in value.items():
                    subanswer[name] = item
                yield subanswer
            else:
                yield from self._analyze_recurse(variables[1:], f'{desc}_{var}_{key}', value, answer)

    def Analyze(self):
        return [answer for answer in self._analyze_recurse(self._variables, self._workload, self._data, {})]
