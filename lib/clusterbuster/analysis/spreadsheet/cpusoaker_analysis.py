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

        def pod_start_delta(data, runtime: str, col: str):
            if runtime in data and 'first_pod_start' in data[runtime]:
                return data[runtime]['last_pod_start'] - data[runtime]['first_pod_start']

        answer += self._analyze_variables(self._data, ['iterations_sec', 'iterations_cpu_sec'], 'CPU (K ops/sec)', divisor=1000, integer=True)
        answer += self._analyze_variables(self._data, 'first_pod_start', 'First pod start (sec)', integer=False, difference=True)
        answer += self._analyze_variables(self._data, 'last_pod_start', 'Last pod start (sec)', integer=False, difference=True)
        answer += self._analyze_variables(self._data, 'memory_per_pod', 'Memory/pod (MiB)', divisor=1048576, integer=False, ratio=False, difference=True)
        answer += self._analyze_variables(self._data, None, 'Last N-1 Pod Start Interval', valfunc=pod_start_delta, integer=False, ratio=True, difference=True)
        return answer
