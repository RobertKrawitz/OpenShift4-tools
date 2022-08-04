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
from math import log, exp


class FilesAnalysisBase(ClusterBusterAnalyzeOne):
    """
    Analyze files data
    """

    def __init__(self, workload: str, data: dict, metadata: dict):
        super().__init__(workload, data, metadata)

    def Analyze(self):
        answer = {
            'workload': self._workload,
            'uuid': self._metadata['uuid'],
            }
        summary = dict()
        count = dict()
        ratio = dict()
        times = dict()
        known_ops = dict()
        known_subops = dict()
        for pods, data1 in self._data.items():
            for dirs, data2 in data1.items():
                for files, data3 in data2.items():
                    for blocksize, data4 in data3.items():
                        for filesize, data5 in data4.items():
                            for direct, data6 in data5.items():
                                if direct == 0:
                                    continue
                                for runtime, data7 in data6.items():
                                    if runtime not in summary:
                                        summary[runtime] = dict()
                                        count[runtime] = dict()
                                        ratio[runtime] = dict()
                                    for op, data8 in data7.items():
                                        known_ops[op] = 1
                                        if op not in times:
                                            times[op] = {}
                                        if op not in summary[runtime]:
                                            summary[runtime][op] = dict()
                                            count[runtime][op] = dict()
                                            ratio[runtime][op] = dict()
                                        for subop, val in data8.items():
                                            known_subops[subop] = 1
                                            if subop not in times[op]:
                                                times[op][subop] = {
                                                    'kata': [],
                                                    'runc': []
                                                    }
                                            times[op][subop][runtime].append(val)
                                            if val > 0:
                                                if subop not in summary[runtime][op]:
                                                    summary[runtime][op][subop] = 0
                                                    count[runtime][op][subop] = 0
                                                    ratio[runtime][op][subop] = 0
                                                count[runtime][op][subop] += 1
                                                summary[runtime][op][subop] += log(val)
        for runtime, data1 in summary.items():
            answer[runtime] = dict()
            for op, data2 in data1.items():
                answer[runtime][op] = dict()
                for subop, data3 in data2.items():
                    answer[runtime][op][subop] = exp(summary[runtime][op][subop] / count[runtime][op][subop])
        answer['ratio'] = dict()
        for op, data1 in answer['runc'].items():
            answer['ratio'][op] = dict()
            for subop, data2 in data1.items():
                answer['ratio'][op][subop] = answer['kata'][op][subop] / answer['runc'][op][subop]
        answer['min_ratio'] = dict()
        answer['max_ratio'] = dict()
        for op in known_ops.keys():
            if op not in times:
                continue
            if op not in answer['min_ratio']:
                answer['min_ratio'][op] = dict()
                answer['max_ratio'][op] = dict()
            for subop in known_subops.keys():
                if subop not in times[op]:
                    continue
                min_ratio = None
                max_ratio = None
                for i in range(len(times[op][subop]['kata'])):
                    if times[op][subop]['kata'][i] > 0 and times[op][subop]['runc'][i] > 0:
                        ratio = times[op][subop]['kata'][i] / times[op][subop]['runc'][i]
                        if min_ratio is None or ratio < min_ratio:
                            min_ratio = ratio
                        if max_ratio is None or ratio > max_ratio:
                            max_ratio = ratio
                answer['min_ratio'][op][subop] = min_ratio
                answer['max_ratio'][op][subop] = max_ratio
        return answer

class files_analysis(FilesAnalysisBase):
    def __init__(self, workload: str, data: dict, metadata: dict):
        super().__init__(workload, data, metadata)
