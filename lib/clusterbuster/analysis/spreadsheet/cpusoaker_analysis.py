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


class cpusoaker_analysis(ClusterBusterAnalyzeOne):
    """
    Analyze cpusoaker data
    """

    def __init__(self, workload: str, data: dict, metadata: dict):
        ClusterBusterAnalyzeOne.__init__(self, workload, data, metadata)

    def Analyze(self):
        answer = f"""Workload: {self._workload}
uuid: {self._metadata['uuid']}
"""

        def pod_start_delta(data: dict, runtime: str, col: str):
            if runtime in data and 'first_pod_start' in data[runtime]:
                return data[runtime]['last_pod_start'] - data[runtime]['first_pod_start']

        answer += self._analyze_variables(self._data, ['iterations_sec', 'iterations_cpu_sec'], 'CPU (K ops/sec)', divisor=1000, integer=True)
        answer += self._analyze_variables(self._data, 'first_pod_start', 'First pod start (sec)', integer=False, difference=True)
        answer += self._analyze_variables(self._data, 'last_pod_start', 'Last pod start (sec)', integer=False, difference=True)
        answer += self._analyze_variables(self._data, 'memory_per_pod', 'Memory/pod (MiB)', divisor=1048576, integer=False, ratio=False, difference=True)
        answer += self._analyze_variables(self._data, None, 'Last N-1 Pod Start Interval', valfunc=pod_start_delta, integer=False, ratio=True, difference=True)
        return answer

    def _analyze_variables(self, data: dict, columns, header: str, divisor = 1.0, valfunc = None, integer: bool=True, ratio: bool=True, difference: bool=False):
        if not isinstance(columns, list):
            columns = [columns]
        pcolumns = []
        for c in columns:
            if c is None:
                pcolumns.append('')
            else:
                pcolumns.append(c)

        column_separator = '\t\t'
        columns_out_base = 'kata\trunc'
        if ratio:
            columns_out_base += '\tratio'
            column_separator += '\t'
        if difference:
            columns_out_base += '\tdelta'
            column_separator += '\t'
        columns_out_1 = '# Pods\t' + column_separator.join(pcolumns)
        columns_out_2 = '# Pods\t' + '\t'.join([columns_out_base for c in pcolumns])

        answer = f"""
{header}, N pods
{columns_out_1}
{columns_out_2}
"""
        rows = []
        for pods, data1 in data.items():
            row = [str(pods)]
            for column in columns:
                if valfunc is not None:
                    runc_value = valfunc(data1, 'runc', column)
                    kata_value = valfunc(data1, 'kata', column)
                else:
                    if 'runc' in data1:
                        runc_value = data1['runc'][column] / divisor
                    else:
                        runc_value = None
                    if 'kata' in data1:
                        kata_value = data1['kata'][column] / divisor
                    else:
                        kata_value = None
                if kata_value:
                    row.append(self._prettyprint(kata_value, base=0, integer=integer))
                else:
                    row.append('')
                if runc_value:
                    row.append(self._prettyprint(runc_value, base=0, integer=integer))
                else:
                    row.append('')
                if runc_value is not None and kata_value is not None:
                    if ratio:
                        row.append(self._prettyprint(kata_value / runc_value, base=0, precision=3))
                    if difference:
                        row.append(self._prettyprint(kata_value - runc_value, base=0, integer=integer, precision=3))
            rows.append('\t'.join(row))
        return answer + '\n'.join(rows) + '\n'
