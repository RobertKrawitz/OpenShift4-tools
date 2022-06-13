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


class fio_analysis(ClusterBusterAnalyzeOne):
    """
    Analyze fio data
    """

    def __init__(self, data: dict, metadata: dict):
        ClusterBusterAnalyzeOne.__init__(self, data, metadata)

    def Analyze(self):
        answers = list()
        for pods, data1 in self._data.items():
            for ioengine, data2 in data1.items():
                for iodepth, data3 in data2.items():
                    for fdatasync, data4 in data3.items():
                        for direct, data5 in data4.items():
                            for pattern, data6 in data5.items():
                                for blocksize, data7 in data6.items():
                                    answer = dict()
                                    answer['pods'] = pods
                                    answer['ioengine'] = ioengine
                                    answer['iodepth'] = iodepth
                                    answer['fdatasync'] = fdatasync
                                    answer['direct'] = direct
                                    answer['pattern'] = pattern
                                    for runtime, data8 in data7.items():
                                        answer[runtime] = data8
                                    if 'kata' in data7 and 'nonkata' in data7:
                                        answer['ratio'] = dict()
                                        for key, subdata in answer['kata'].items():
                                            answer['ratio'][key] = dict()
                                            for subkey in subdata.keys():
                                                answer['ratio'][key][subkey] = (data7['kata'][key][subkey] /
                                                                                data7['nonkata'][key][subkey])
                                answers.append(answer)
        return answers
