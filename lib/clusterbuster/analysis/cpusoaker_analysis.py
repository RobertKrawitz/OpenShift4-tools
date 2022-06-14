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

from lib.clusterbuster.analysis.ClusterBusterAnalysis import ClusterBusterAnalyzeOne


class cpusoaker_analysis(ClusterBusterAnalyzeOne):
    """
    Analyze cpusoaker data
    """

    def __init__(self, data: dict, metadata: dict):
        ClusterBusterAnalyzeOne.__init__(self, data, metadata)

    def Analyze(self):
        answers = list()
        for pods, data1 in self._data.items():
            for runtime, data2 in data1.items():
                answer = dict()
                answer['test_description'] = dict()
                answer['test_description']['workload'] = 'cpusoaker'
                answer['test_description']['pods'] = pods
                answer['test_description']['runtime'] = runtime
                answer['test_description']['name'] = f'cpusoaker_xb{runtime}_pods_{pods}'
                for key, item in data2.items():
                    answer[key] = item
                answers.append(answer)
        return answers
