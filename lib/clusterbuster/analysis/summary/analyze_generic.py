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
    Analyze data from multi-dimensional workloads
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

    def __accumulate(self, accumulator: dict, runtime: str, dimension: str, dim_value: str, variable: str, var_value: float):
        if dimension not in accumulator:
            accumulator[dimension] = {}
        if variable not in accumulator[dimension]:
            accumulator[dimension][variable] = {}
        if dim_value not in accumulator[dimension][variable]:
            accumulator[dimension][variable][dim_value] = {}
        if runtime not in accumulator[dimension][variable][dim_value]:
            accumulator[dimension][variable][dim_value][runtime] = {
                'sum': 0,
                'count': 0,
                'values': [],
                }
        accumulator[dimension][variable][dim_value][runtime]['values'].append(var_value)
        accumulator[dimension][variable][dim_value][runtime]['sum'] += log(var_value)
        accumulator[dimension][variable][dim_value][runtime]['count'] += 1

    def __report_one_dimension(self, accumulator: dict):
        answer = dict()
        for variable in self._variables:
            min_ratio = None
            max_ratio = None
            if variable not in accumulator:
                continue
            if variable not in answer:
                answer[variable] = {}
            for key, value in accumulator[variable].items():
                for runtime in self._runtimes:
                    if runtime not in value:
                        continue
                    value1 = value[runtime]
                    if 'count' not in value1 or value1['count'] == 0:
                        continue
                    if runtime not in answer[variable]:
                        answer[variable][runtime] = {}
                    answer[variable][runtime][key] = exp(value1['sum'] / value1['count'])
                if 'kata' in answer[variable] and 'runc' in answer[variable]:
                    ratio = answer[variable]['kata'][key] / answer[variable]['runc'][key]
                    if 'ratio' not in answer[variable]:
                        answer[variable]['ratio'] = {}
                    answer[variable]['ratio'][key] = ratio
                min_ratio = None
                max_ratio = None
                for i in range(len(value['runc']['values'])):
                    ratio = value['kata']['values'][i] / value['runc']['values'][i]
                    if min_ratio is None or ratio < min_ratio:
                        min_ratio = ratio
                    if max_ratio is None or ratio > max_ratio:
                        max_ratio = ratio
                    if 'max_ratio' not in answer[variable]:
                        answer[variable]['min_ratio'] = {}
                        answer[variable]['max_ratio'] = {}
                    answer[variable]['min_ratio'][key] = min_ratio
                    answer[variable]['max_ratio'][key] = max_ratio
        return answer

    def __report(self, accumulator: dict):
        answer = {
            'workload': self._workload,
            'uuid': self._metadata['uuid']
            }
        for dimension in self._dimensions:
            if dimension in accumulator:
                answer[dimension] = self.__report_one_dimension(accumulator[dimension])
        answer['Overall'] = self.__report_one_dimension(accumulator['Overall'])
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
                for var in self._variables:
                    ratio = {}
                    for runtime, data in value.items():
                        datum = self._retrieve_datum(var, data)
                        if (datum > 0):
                            ratio[runtime] = datum
                            for dimension, dim_value in values.items():
                                self.__accumulate(accumulator, runtime, dimension, dim_value, var, datum)
                            self.__accumulate(accumulator, runtime, 'Overall', True, var, datum)

    def Analyze(self):
        accumulator = dict()
        self.__analyze_one(accumulator, self._data, dict(), self._dimensions)
        return self.__report(accumulator)
