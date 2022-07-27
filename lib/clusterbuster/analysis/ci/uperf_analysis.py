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

from ..ClusterBusterAnalysis import ClusterBusterAnalyzeOne


class uperf_analysis(ClusterBusterAnalyzeOne):
    """
    Analyze uperf data
    """

    def __init__(self, workload: str, data: dict, metadata: dict):
        ClusterBusterAnalyzeOne.__init__(self, workload, data, metadata)

    def Analyze(self):
        answers = list()
        for pods, data1 in self._data.items():
            for msgsize, data2 in data1.items():
                for threads, data3 in data2.items():
                    for runtime, data4 in data3.items():
                        answer = dict()
                        answer['uuid'] = self._metadata['uuid']
                        answer['test_description'] = dict()
                        answer['test_description']['pods'] = pods
                        answer['test_description']['workload'] = 'uperf'
                        answer['test_description']['msgsize'] = msgsize
                        answer['test_description']['threads'] = threads
                        answer['test_description']['runtime'] = runtime
                        answer['test_description']['name'] = f'uperf_{runtime}_pods_{pods}_msgsize_{msgsize}_threads_{threads}'
                        for key, item in data4.items():
                            answer[key] = item
                        answers.append(answer)
        return answers
