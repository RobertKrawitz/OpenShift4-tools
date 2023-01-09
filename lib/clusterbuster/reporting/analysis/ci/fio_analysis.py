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


class fio_analysis(ClusterBusterAnalyzeOne):
    """
    Analyze fio data
    """

    def __init__(self, workload: str, data: dict, metadata: dict):
        super().__init__(workload, data, metadata)

    def Analyze(self):
        answers = list()
        for pods, data1 in self._data.items():
            for ioengine, data2 in data1.items():
                for iodepth, data3 in data2.items():
                    for fdatasync, data4 in data3.items():
                        for direct, data5 in data4.items():
                            for pattern, data6 in data5.items():
                                for blocksize, data7 in data6.items():
                                    for run, data8 in data7.items():
                                        answer = dict()
                                        answer['uuid'] = self._metadata['jobs'][run]['uuid']
                                        answer['test_description'] = dict()
                                        answer['test_description']['pods'] = pods
                                        answer['test_description']['workload'] = 'fio'
                                        answer['test_description']['ioengine'] = ioengine
                                        answer['test_description']['iodepth'] = iodepth
                                        answer['test_description']['fdatasync'] = fdatasync
                                        answer['test_description']['direct'] = direct
                                        answer['test_description']['pattern'] = pattern
                                        answer['test_description']['blocksize'] = blocksize
                                        answer['test_description']['runtime'] = run
                                        answer['test_description']['name'] = f'fio_pods_{pods}_ioengine_{ioengine}_iodepth_{iodepth}_fdatasync_{fdatasync}_direct_{direct}_pattern_{pattern}_blocksize_{blocksize}'
                                        for key, item in data8.items():
                                            answer[key] = item
                                        answers.append(answer)
        return answers
