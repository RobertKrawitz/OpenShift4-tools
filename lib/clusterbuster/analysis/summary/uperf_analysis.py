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


class uperf_analysis(ClusterBusterAnalyzeOne):
    """
    Analyze uperf data
    """

    def __init__(self, workload: str, data: dict, metadata: dict):
        ClusterBusterAnalyzeOne.__init__(self, workload, data, metadata)

    def __accumulate(self, accumulator: dict, runtime: str, var, varvalue, acctype, value):
        if var not in accumulator:
            accumulator[var] = {}
        if varvalue not in accumulator[var]:
            accumulator[var][varvalue] = {}
        if runtime not in accumulator[var][varvalue]:
            accumulator[var][varvalue][runtime] = {}
        if acctype not in accumulator[var][varvalue][runtime]:
            accumulator[var][varvalue][runtime][acctype] = {
                                                            'sum': 0,
                                                            'count': 0
                                                            }
        accumulator[var][varvalue][runtime][acctype]['sum'] += value
        accumulator[var][varvalue][runtime][acctype]['count'] += 1

    def Analyze(self):
        dimensions = ['By Message Size', 'By Pod Count', 'By Threads', 'Overall']
        runtimes = ['kata', 'runc']
        variables = ['rate', 'ops_sec']
        answer = {
            'workload': self._workload,
            'uuid': self._metadata['uuid']
            }
        accumulator = dict()
        for dimension in dimensions:
            answer[dimension] = dict()
            accumulator[dimension] = dict()
        for pods, data1 in self._data.items():
            for msgsize, data2 in data1.items():
                for threads, data3 in data2.items():
                    for runtime, data4 in data3.items():
                        if runtime not in runtimes:
                            continue
                        for variable in variables:
                            if data4[variable] > 0:
                                log_value = log(data4[variable])
                                self.__accumulate(accumulator, runtime, 'By Pod Count', pods, variable, log_value)
                                self.__accumulate(accumulator, runtime, 'By Message Size', msgsize, variable, log_value)
                                self.__accumulate(accumulator, runtime, 'By Threads', threads, variable, log_value)
                                self.__accumulate(accumulator, runtime, 'Overall', True, variable, log_value)

        for dimension in dimensions:
            for key, value in accumulator[dimension].items():
                for runtime in runtimes:
                    value1 = value.get(runtime, None)
                    if value1 is None:
                        continue
                    for variable in variables:
                        if variable not in value1 or 'count' not in value1[variable] or value1[variable]['count'] == 0:
                            continue
                        if dimension == 'Overall':
                            if runtime not in answer[dimension]:
                                answer[dimension][runtime] = {}
                            answer[dimension][runtime][variable] = exp(value1[variable]['sum'] / value1[variable]['count'])
                        else:
                            if key not in answer[dimension]:
                                answer[dimension][key] = {}
                            if runtime not in answer[dimension][key]:
                                answer[dimension][key][runtime] = {}
                            answer[dimension][key][runtime][variable] = exp(value1[variable]['sum'] / value1[variable]['count'])
            if dimension == 'Overall':
                answer[dimension]['ratio'] = dict()
                for variable in variables:
                    if variable in answer[dimension]['kata'] and variable in answer[dimension]['runc']:
                        answer[dimension]['ratio'][variable] = answer[dimension]['kata'][variable] / answer[dimension]['runc'][variable]
            else:
                for key, value in accumulator[dimension].items():
                    answer[dimension][key]['ratio'] = dict()
                    for variable in variables:
                        if variable in answer[dimension][key]['kata'] and variable in answer[dimension][key]['runc']:
                            answer[dimension][key]['ratio'][variable] = answer[dimension][key]['kata'][variable] / answer[dimension][key]['runc'][variable]
        return answer
