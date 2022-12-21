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
        self._baseline = self._metadata['baseline']

    def Analyze(self):
        answer = {
            'workload': self._workload,
            }
        max_pods = dict()
        memory = dict()
        pods_sec = dict()
        iterations_sec = dict()
        iterations_cpu_sec = dict()
        min_pod_start_time = dict()
        max_pod_start_time = dict()
        first_pod_start = dict()
        last_pod_start = dict()
        for pods, data1 in self._data.items():
            for runtime, data2 in data1.items():
                if runtime not in max_pods:
                    max_pods[runtime] = 0
                    memory[runtime] = dict()
                    pods_sec[runtime] = dict()
                    iterations_sec[runtime] = dict()
                    iterations_cpu_sec[runtime] = dict()
                    first_pod_start[runtime] = dict()
                    last_pod_start[runtime] = dict()
                    min_pod_start_time[runtime] = None
                    max_pod_start_time[runtime] = None
                if min_pod_start_time[runtime] is None or data2['first_pod_start'] < min_pod_start_time[runtime]:
                    min_pod_start_time[runtime] = data2['first_pod_start']
                if max_pod_start_time[runtime] is None or data2['first_pod_start'] > max_pod_start_time[runtime]:
                    max_pod_start_time[runtime] = data2['first_pod_start']
                if pods > max_pods[runtime]:
                    max_pods[runtime] = pods
                try:
                    memory[runtime][pods] = data2['memory_per_pod']
                except Exception:
                    pass
                pods_sec[runtime][pods] = data2['pod_starts_per_second']
                first_pod_start[runtime][pods] = data2['first_pod_start']
                last_pod_start[runtime][pods] = data2['last_pod_start']
                iterations_sec[runtime][pods] = data2['iterations_sec']
                iterations_cpu_sec[runtime][pods] = data2['iterations_cpu_sec']
        min_max_pods = None
        for runtime in max_pods:
            answer[runtime] = dict()
            answer[runtime]['Max Pods'] = max_pods[runtime]
            if min_max_pods is None or max_pods[runtime] < min_max_pods:
                min_max_pods = max_pods[runtime]
        for runtime in max_pods:
            answer[runtime]['Pod starts/sec'] = pods_sec[runtime][min_max_pods]
            answer[runtime]['Iterations/sec'] = iterations_sec[runtime][min_max_pods]
            answer[runtime]['Iterations/CPU sec'] = iterations_cpu_sec[runtime][min_max_pods]
            try:
                answer[runtime]['Per-pod memory'] = int(memory[runtime][min_max_pods])
            except Exception:
                pass
            answer[runtime]['Fastest pod start'] = min_pod_start_time[runtime]
            answer[runtime]['Slowest pod start'] = max_pod_start_time[runtime]
            answer[runtime]['Last n-1 pod start time'] = last_pod_start[runtime][min_max_pods] - first_pod_start[runtime][min_max_pods]
            if runtime != self._baseline and self._baseline in answer:
                try:
                    answer[runtime]['Ratio pod starts/sec'] = pods_sec[runtime][min_max_pods] / pods_sec[self._baseline][min_max_pods]
                    answer[runtime]['Ratio iterations/CPU sec'] = iterations_cpu_sec[runtime][min_max_pods] / iterations_sec[self._baseline][min_max_pods]
                    answer[runtime]['Ratio iterations/CPU sec'] = iterations_cpu_sec[runtime][min_max_pods] / iterations_cpu_sec[self._baseline][min_max_pods]
                    answer[runtime]['Ratio fastest pod start time'] = min_pod_start_time[runtime] / min_pod_start_time[self._baseline]
                    answer[runtime]['Ratio slowest pod start time'] = max_pod_start_time[runtime] / max_pod_start_time[self._baseline]
                    answer[runtime]['Ratio last n-1 pod start time'] = answer[runtime]['Last n-1 pod start time'] / answer[self._baseline]['Last n-1 pod start time']
                    answer[runtime]['First pod start overhead'] = min_pod_start_time[runtime] - min_pod_start_time[self._baseline]
                    answer[runtime]['Memory overhead/pod'] = int(memory[runtime][min_max_pods] - memory[self._baseline][min_max_pods])
                except Exception:
                    pass
        return answer
