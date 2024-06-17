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
from ...prettyprint import prettyprint


class cpusoaker_analysis(ClusterBusterAnalyzeOneBase):
    """
    Analyze cpusoaker data
    """

    def __init__(self, workload: str, data: dict, metadata: dict):
        super().__init__(workload, data, metadata)

    def get_value(self, data: dict, run: str, col: str, valfunc=None):
        if valfunc is not None:
            return valfunc(data, run, col)
        else:
            return self._safe_get(data, [run, col], '')

    def Analyze(self):
        answer = f"""Workload: {self._workload}
"""

        def pod_start_delta(data: dict, run: str, col: str):
            if run in data and 'first_pod_start' in data[run]:
                return data[run]['last_pod_start'] - data[run]['first_pod_start']
            else:
                return ''

        answer += self._analyze_variables(self._data, 'iterations_sec',
                                          'CPU (K iterations/sec)', multiplier=.001, integer=True)
        answer += self._analyze_variables(self._data, 'iterations_cpu_sec',
                                          'CPU (K iterations/CPU sec)', multiplier=.001, integer=True)
        answer += self._analyze_variables(self._data, 'first_pod_start', 'First pod start (sec)',
                                          integer=False, difference=True)
        answer += self._analyze_variables(self._data, 'last_pod_start', 'Last pod start (sec)',
                                          integer=False, difference=True, rate_per_second=True)
        answer += self._analyze_variables(self._data, 'memory_per_pod', 'Memory/pod (MiB)',
                                          multiplier=1/1048576, integer=False, ratio=False, difference=True)
        answer += self._analyze_variables(self._data, None, 'Last N-1 Pod Start Interval',
                                          valfunc=pod_start_delta, integer=False, ratio=True, difference=True)
        return answer

    def _analyze_variables(self, data: dict, column, header: str, multiplier=1.0, valfunc=None,
                           integer: bool = True, ratio: bool = True, difference: bool = False,
                           rate_per_second: bool = False):

        def isnumber(x):
            return isinstance(x, (int, float))

        tab = '\t'                        # for F-strings

        runs = list(self._metadata['jobs'].keys())
        columns_txt = f'# Pods{tab}{runs[0]}'
        # This just gets too hairy with list comprehension
        for run in runs[1:]:
            columns_txt += f'{tab}{run}'

        answer = f"""
{header}, N pods
{columns_txt}
"""
        rows = []
        for pods, data1 in sorted(list(data.items())):
            row = [str(pods)]
            for run in runs:
                run_value = self.get_value(data1, run, column, valfunc)
                row.append(prettyprint(run_value,  base=0, integer=integer, precision=3, multiplier=multiplier))
            rows.append('\t'.join(row))
        answer += '\n'.join(rows) + '\n'

        if ratio:
            answer += f"""
{header}, N pods (ratio)
{columns_txt}
"""
            rows = []
            for pods, data1 in sorted(list(data.items())):
                baseline_value = self.get_value(data1, runs[0], column, valfunc)
                row = [str(pods), '']
                for run in runs[1:]:
                    run_value = self.get_value(data1, run, column, valfunc)
                    run_ratio = run_value / baseline_value if (isnumber(baseline_value) and
                                                               baseline_value > 0 and isnumber(run_value)) else ''
                    row.append(prettyprint(run_ratio, base=0, precision=3))
                rows.append('\t'.join(row))
            answer += '\n'.join(rows) + '\n'

        if difference:
            answer += f"""
{header}, N pods (delta)
{columns_txt}
"""
            rows = []
            for pods, data1 in sorted(list(data.items())):
                baseline_value = self.get_value(data1, runs[0], column, valfunc)
                row = [str(pods), '']
                for run in runs[1:]:
                    run_value = self.get_value(data1, run, column, valfunc)
                    run_delta = run_value - baseline_value if (isnumber(baseline_value) and baseline_value > 0
                                                               and isnumber(run_value)) else ''
                    row.append(prettyprint(run_delta, base=0, integer=integer, precision=3, multiplier=multiplier))
                rows.append('\t'.join(row))
            answer += '\n'.join(rows) + '\n'

        if rate_per_second:
            answer += f"""
{header}, N pods (starts per second)
{columns_txt}
"""
            rows = []
            for pods, data1 in sorted(list(data.items())):
                row = [str(pods)]
                for run in runs:
                    run_value = self.get_value(data1, run, column, valfunc)
                    per_second = int(pods) / run_value if isnumber(run_value) and run_value > 0 else ''
                    row.append(prettyprint(per_second, base=0, integer=integer, precision=3, multiplier=multiplier))
                rows.append('\t'.join(row))
            answer += '\n'.join(rows) + '\n'

        return answer
