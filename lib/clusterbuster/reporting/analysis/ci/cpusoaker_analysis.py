#!/usr/bin/env python3
# Copyright 2022-2023 Robert Krawitz/Red Hat
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

from ..ClusterBusterAnalysis import ClusterBusterAnalyzeOne


class cpusoaker_analysis(ClusterBusterAnalyzeOne):
    """
    Analyze cpusoaker data
    """

    def __init__(self, workload: str, data: dict, metadata: dict):
        super().__init__(workload, data, metadata)

    def Analyze(self):
        answers = list()
        for pods, data1 in self._data.items():
            for run, data2 in data1.items():
                answer = dict()
                answer['uuid'] = self._metadata['jobs'][run]['uuid']
                answer['test_description'] = dict()
                answer['test_description']['workload'] = 'cpusoaker'
                answer['test_description']['pods'] = pods
                answer['test_description']['runtime'] = run
                answer['test_description']['name'] = f'cpusoaker_{run}_pods_{pods}'
                for key, item in data2.items():
                    answer[key] = item
                answers.append(answer)
        return answers
