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


class files_analysis(ClusterBusterAnalyzeOne):
    """
    Analyze files data
    """

    def __init__(self, workload: str, data: dict, metadata: dict):
        super().__init__(workload, data, metadata)

    def Analyze(self):
        answers = list()
        for pods, data1 in self._data.items():
            for dirs, data2 in data1.items():
                for files, data3 in data2.items():
                    for blocksize, data4 in data3.items():
                        for filesize, data5 in data4.items():
                            for direct, data6 in data5.items():
                                answer = dict()
                                answer['test_description'] = dict()
                                answer['test_description']['pods'] = pods
                                answer['test_description']['dirs'] = dirs
                                answer['test_description']['workload'] = 'files'
                                answer['test_description']['files'] = files
                                answer['test_description']['filesize'] = filesize
                                answer['test_description']['blocksize'] = blocksize
                                answer['test_description']['direct'] = direct
                                answer['test_description']['name'] = f'files_pods_{pods}_dirs_{dirs}_files_{files}_blocksize_{blocksize}_direct_{direct}'
                                for key, item in data6.items():
                                    answer[key] = item
                                answers.append(answer)
        return answers
