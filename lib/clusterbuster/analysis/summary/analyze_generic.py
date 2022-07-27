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


class ClusterBusterAnalyzeSummaryGeneric(ClusterBusterAnalyzeOne):
    """
    Analyze fio data
    """

    def __init__(self, workload: str, data: dict, metadata: dict, dimensions: list, variables: list,
                 filters: dict = None, runtimes: list = ['kata', 'runc']):
        ClusterBusterAnalyzeOne.__init__(self, workload, data, metadata)
        self._dimensions = dimensions
        self._variables = variables
        self._runtimes = runtimes
        self._filters = filters

    def _retrieve_datum(self, var: str, value: dict):
        return value.get(var, 0)

    def __accumulate(self, accumulator: dict, runtime: str, dimension: str, dim_value: str, variable: str, var_value: str):
        if dimension not in accumulator:
            accumulator[dimension] = {}
        if dim_value not in accumulator[dimension]:
            accumulator[dimension][dim_value] = {}
        if runtime not in accumulator[dimension][dim_value]:
            accumulator[dimension][dim_value][runtime] = {}
        if variable not in accumulator[dimension][dim_value][runtime]:
            accumulator[dimension][dim_value][runtime][variable] = {
                                                            'sum': 0,
                                                            'count': 0
                                                            }
        accumulator[dimension][dim_value][runtime][variable]['sum'] += var_value
        accumulator[dimension][dim_value][runtime][variable]['count'] += 1

    def __report_one_dimension(self, accumulator: dict):
        answer = dict()
        for key, value in accumulator.items():
            for runtime in self._runtimes:
                value1 = value.get(runtime, None)
                if value1 is None:
                    continue
                for variable in self._variables:
                    if variable not in value1 or 'count' not in value1[variable] or value1[variable]['count'] == 0:
                        continue
                    if key not in answer:
                        answer[key] = {}
                    if runtime not in answer[key]:
                        answer[key][runtime] = {}
                    answer[key][runtime][variable] = exp(value1[variable]['sum'] / value1[variable]['count'])
        for key, value in accumulator.items():
            answer[key]['ratio'] = dict()
            for variable in self._variables:
                if variable in answer[key]['kata'] and variable in answer[key]['runc']:
                    answer[key]['ratio'][variable] = answer[key]['kata'][variable] / answer[key]['runc'][variable]
        return answer

    def __report_overall(self, accumulator):
        answer = dict()
        for key, value in accumulator.items():
            for runtime in self._runtimes:
                value1 = value.get(runtime, None)
                if value1 is None:
                    continue
                for variable in self._variables:
                    if variable not in value1 or 'count' not in value1[variable] or value1[variable]['count'] == 0:
                        continue
                    if runtime not in answer:
                        answer[runtime] = {}
                    answer[runtime][variable] = exp(value1[variable]['sum'] / value1[variable]['count'])
        answer['ratio'] = dict()
        for variable in self._variables:
            if variable in answer['kata'] and variable in answer['runc']:
                answer['ratio'][variable] = answer['kata'][variable] / answer['runc'][variable]
        return answer

    def __report(self, accumulator: dict):
        answer = {
            'workload': self._workload,
            'uuid': self._metadata['uuid']
            }
        for dimension in self._dimensions:
            if dimension in accumulator:
                answer[dimension] = self.__report_one_dimension(accumulator[dimension])
        answer['Overall'] = self.__report_overall(accumulator['Overall'])
        return answer

    def __analyze_one(self, accumulator: dict, data: dict, values: dict, dimensions: list):
        dimension = dimensions[0]
        ignore = False
        if dimension.startswith('-'):
            ignore = True
            dimension = dimension[1:]
        for key, value in data.items():
            if self._filters is not None and dimension in self._filters and not self._filters[dimension](dimension, value):
                continue
            if not ignore:
                values[dimension] = key
            if len(dimensions) > 1:
                self.__analyze_one(accumulator, value, values, dimensions[1:])
            else:
                for runtime, data in value.items():
                    for var in self._variables:
                        datum = self._retrieve_datum(var, data)
                        if (datum > 0):
                            log_datum = log(datum)
                            for dimension, dim_value in values.items():
                                self.__accumulate(accumulator, runtime, dimension, dim_value, var, log_datum)
                            self.__accumulate(accumulator, runtime, 'Overall', True, var, log_datum)

    def Analyze(self):
        accumulator = dict()
        self.__analyze_one(accumulator, self._data, dict(), self._dimensions)
        return self.__report(accumulator)
