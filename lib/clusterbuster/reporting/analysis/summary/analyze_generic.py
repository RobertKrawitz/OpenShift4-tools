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

from ..ClusterBusterAnalysis import ClusterBusterAnalyzeOneBase
from math import log, exp


class ClusterBusterAnalyzeSummaryGeneric(ClusterBusterAnalyzeOneBase):
    """
    Analyze data from multi-dimensional workloads
    """

    def __init__(self, workload: str, data: dict, metadata: dict, dimensions: list, variables: list,
                 filters: dict = None, runs: list = None, baseline: str = None):
        super().__init__(workload, data, metadata)
        self._dimensions = dimensions
        self._variables = variables
        if runs:
            self._runs = runs
        else:
            self._runs = metadata['jobs'].keys()
        if baseline:
            self._baseline = baseline
        else:
            self._baseline = metadata['baseline']
        if self._baseline not in self._runs:
            raise ValueError(f"Baseline run {self._baseline} must be in run list {self._runs}")
        self._filters = filters

    def _retrieve_datum(self, var: str, value: dict):
        return value.get(var, None)

    def __accumulate(self, accumulator: dict, run: str, dimension: str, dim_value: str, variable: str, var_value: float):
        if dimension not in accumulator:
            accumulator[dimension] = {}
        if variable not in accumulator[dimension]:
            accumulator[dimension][variable] = {}
        if dim_value not in accumulator[dimension][variable]:
            accumulator[dimension][variable][dim_value] = {}
        if run not in accumulator[dimension][variable][dim_value]:
            accumulator[dimension][variable][dim_value][run] = {
                'sum': 0,
                'count': 0,
                'values': [],
                }
        accumulator[dimension][variable][dim_value][run]['values'].append(var_value)
        accumulator[dimension][variable][dim_value][run]['sum'] += log(var_value)
        accumulator[dimension][variable][dim_value][run]['count'] += 1

    def __report_one_dimension(self, accumulator: dict):
        answer = dict()
        for variable in self._variables:
            if variable not in accumulator:
                continue
            if variable not in answer:
                answer[variable] = {}
            for key, value in accumulator[variable].items():
                for run in self._runs:
                    if run not in value:
                        continue
                    value1 = value[run]
                    if 'count' not in value1 or value1['count'] == 0:
                        continue
                    if run not in answer[variable]:
                        answer[variable][run] = {}
                    if key not in answer[variable][run]:
                        answer[variable][run][key] = {}
                    answer[variable][run][key]['value'] = exp(value1['sum'] / value1['count'])
                    if ((run != self._baseline and run in answer[variable] and self._baseline in answer[variable] and
                         key in answer[variable][run] and key in answer[variable][self._baseline])):
                        ratio = answer[variable][run][key]['value'] / answer[variable][self._baseline][key]['value']
                        answer[variable][run][key]['ratio'] = ratio
                        min_ratio = None
                        max_ratio = None
                        for i in range(len(value[self._baseline]['values'])):
                            if run not in value or i >= len(value[run]['values']):
                                continue
                            ratio = value[run]['values'][i] / value[self._baseline]['values'][i]
                            if min_ratio is None or ratio < min_ratio:
                                min_ratio = ratio
                            if max_ratio is None or ratio > max_ratio:
                                max_ratio = ratio
                            answer[variable][run][key]['min_ratio'] = min_ratio
                            answer[variable][run][key]['max_ratio'] = max_ratio
        return answer

    def __report(self, accumulator: dict):
        answer = {
            'workload': self._workload,
            }
        for dimension in self._dimensions:
            if dimension in accumulator:
                answer[dimension] = self.__report_one_dimension(accumulator[dimension])
        answer['Overall'] = self.__report_one_dimension(accumulator.get('Overall', []))
        return answer

    def __analyze_one(self, accumulator: dict, detail: dict, data: dict, values: dict, dimensions: list, case_name: str = None):
        dimension = dimensions[0]
        ignore = False
        if dimension.startswith('-'):
            ignore = True
            dimension = dimension[1:]
        for key, value in data.items():
            if self._filters is not None and dimension in self._filters and not self._filters[dimension](dimension, value):
                continue
            if ignore:
                out_case_name = case_name
            else:
                case_label = dimension.replace('By ', '') + ': ' + str(key)
                values[dimension] = key
                if case_name is None:
                    out_case_name = case_label
                else:
                    out_case_name = case_name + ", " + case_label
            if len(dimensions) > 1:
                self.__analyze_one(accumulator, detail, value, values, dimensions[1:], case_name=out_case_name)
            else:
                detail_row = dict()
                for var in self._variables:
                    detail_row[var] = {}
                    ratio = {}
                    for run, data in value.items():
                        detail_row[var][run] = {}
                        datum = self._retrieve_datum(var, data)
                        if datum is not None and datum > 0:
                            detail_row[var][run]['value'] = datum
                            ratio[run] = datum
                            for dimension, dim_value in values.items():
                                self.__accumulate(accumulator, run, dimension, dim_value, var, datum)
                            self.__accumulate(accumulator, run, 'Overall', 'Total', var, datum)
                            if ((run != self._baseline and run in detail_row[var] and
                                 'value' in detail_row[var][run] and
                                 self._baseline in detail_row[var] and
                                 'value' in detail_row[var][self._baseline] and
                                 detail_row[var][self._baseline]['value'] > 0)):
                                detail_row[var][run]['ratio'] = (detail_row[var][run]['value'] /
                                                                 detail_row[var][self._baseline]['value'])
                detail[out_case_name] = detail_row

    def Analyze(self, report_summary: bool = True, report_detail: bool = False):
        accumulator = dict()
        detail = dict()
        self.__analyze_one(accumulator, detail, self._data, dict(), self._dimensions)
        if report_summary:
            if report_detail:
                return self.__report(accumulator), detail
            else:
                return self.__report(accumulator)
        else:
            if report_detail:
                return detail
