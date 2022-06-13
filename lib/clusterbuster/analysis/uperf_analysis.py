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


class uperf_analysis(ClusterBusterAnalyzeOne):
    """
    Analyze uperf data
    """

    def __init__(self, data: dict, metadata: dict):
        ClusterBusterAnalyzeOne.__init__(self, data, metadata)

    def Analyze(self):
        answers = list()
        for pods, data1 in self._data.items():
            for msgsize, data2 in data1.items():
                for threads, data3 in data2.items():
                    answer = dict()
                    answer['pods'] = pods
                    answer['msgsize'] = msgsize
                    answer['threads'] = threads
                    for runtime, data4 in data3.items():
                        answer[runtime] = data4
                    if 'kata' in data4 and 'nonkata' in data4:
                        answer['ratio'] = dict()
                        for key in answer['kata'].keys():
                            answer['ratio'][key] = data3['kata'][key] / data3['nonkata'][key]
                    answers.append(answer)
        return answers
