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


class fio_analysis(ClusterBusterAnalyzeOne):
    """
    Analyze fio data
    """

    def __init__(self, data: dict, metadata: dict):
        ClusterBusterAnalyzeOne.__init__(self, data, metadata)

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
        dimensions = ['By Engine', 'By Pod Count', 'By I/O Depth', 'By Operation', 'By Blocksize', 'Overall']
        runtimes = ['kata', 'runc']
        variables = ['throughput', 'iops']
        answer = {
            'workload': 'fio',
            'uuid': self._metadata['uuid']
            }
        accumulator = dict()
        for dimension in dimensions:
            answer[dimension] = dict()
            accumulator[dimension] = dict()
        for pods, data1 in self._data.items():
            for ioengine, data2 in data1.items():
                for iodepth, data3 in data2.items():
                    for fdatasync, data4 in data3.items():
                        for direct, data5 in data4.items():
                            if direct == 0:
                                continue
                            for pattern, data6 in data5.items():
                                for blocksize, data7 in data6.items():
                                    for runtime, data8 in data7.items():
                                        if runtime not in runtimes or 'total' not in data8:
                                            continue
                                        for variable in variables:
                                            if data8['total'].get(variable, 0) > 0:
                                                log_value = log(data8['total'][variable])
                                                self.__accumulate(accumulator, runtime, 'By Engine', ioengine, variable, log_value)
                                                self.__accumulate(accumulator, runtime, 'By Pod Count', pods, variable, log_value)
                                                self.__accumulate(accumulator, runtime, 'By I/O Depth', iodepth, variable, log_value)
                                                self.__accumulate(accumulator, runtime, 'By Operation', pattern, variable, log_value)
                                                self.__accumulate(accumulator, runtime, 'By Blocksize', blocksize, variable, log_value)
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
