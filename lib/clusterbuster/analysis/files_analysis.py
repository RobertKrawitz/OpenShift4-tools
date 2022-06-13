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


class files_analysis(ClusterBusterAnalyzeOne):
    """
    Analyze files data
    """

    def __init__(self, data: dict, metadata: dict):
        ClusterBusterAnalyzeOne.__init__(self, data, metadata)

    def Analyze(self):
        answers = list()
        for pods, data1 in self._data.items():
            for dirs, data2 in data1.items():
                for files, data3 in data2.items():
                    for blocksize, data4 in data3.items():
                        for blocks, data5 in data4.items():
                            for direct, data6 in data5.items():
                                answer = dict()
                                answer['pods'] = pods
                                answer['files'] = files
                                answer['blocks'] = blocks
                                answer['blocksize'] = blocksize
                                answer['direct'] = direct
                                for runtime, data7 in data6.items():
                                    answer[runtime] = data7
                                if 'kata' in data6 and 'nonkata' in data6:
                                    answer['ratio'] = dict()
                                    for key, subdata in answer['kata'].items():
                                        answer['ratio'][key] = dict()
                                        for subkey in subdata.keys():
                                            if data6['nonkata'][key][subkey] > 0:
                                                answer['ratio'][key][subkey] = (data6['kata'][key][subkey] /
                                                                                data6['nonkata'][key][subkey])
                                            else:
                                                answer['ratio'][key][subkey] = 0
                                answers.append(answer)
        return answers
