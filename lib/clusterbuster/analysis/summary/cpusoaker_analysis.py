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

    def __init__(self, data: dict, metadata: dict):
        ClusterBusterAnalyzeOne.__init__(self, data, metadata)

    def Analyze(self):
        answer = dict()
        answer['workload'] = 'cpusoaker'
        answer['uuid'] = self._metadata['uuid']
        max_pods = dict()
        memory = dict()
        pods_sec = dict()
        iterations_sec = dict()
        iterations_cpu_sec = dict()
        for pods, data1 in self._data.items():
            for runtime, data2 in data1.items():
                if runtime not in max_pods:
                    max_pods[runtime] = 0
                    memory[runtime] = dict()
                    pods_sec[runtime] = dict()
                    iterations_sec[runtime] = dict()
                    iterations_cpu_sec[runtime] = dict()
                if pods > max_pods[runtime]:
                    max_pods[runtime] = pods
                memory[runtime][pods] = data2['memory_per_pod']
                pods_sec[runtime][pods] = data2['pod_starts_per_second']
                iterations_sec[runtime][pods] = data2['iterations_sec']
                iterations_cpu_sec[runtime][pods] = data2['iterations_cpu_sec']
        min_max_pods = None
        for runtime in max_pods:
            answer[f'Max Pods {runtime}'] = max_pods[runtime]
            if min_max_pods is None or max_pods[runtime] < min_max_pods:
                min_max_pods = max_pods[runtime]
        for runtime in max_pods:
            answer[runtime] = dict()
            answer[runtime]['Pod starts/sec'] = pods_sec[runtime][min_max_pods]
            answer[runtime]['Iterations/sec'] = iterations_sec[runtime][min_max_pods]
            answer[runtime]['Iterations/CPU sec'] = iterations_cpu_sec[runtime][min_max_pods]
            answer[runtime]['Per-pod memory'] = memory[runtime][min_max_pods]
        answer['Kata memory overhead/pod'] = memory['kata'][min_max_pods] - memory['runc'][min_max_pods]
        answer['Ratio pod starts/sec'] = pods_sec['kata'][min_max_pods] / pods_sec['runc'][min_max_pods]
        answer['Ratio iterations/CPU sec'] = iterations_cpu_sec['kata'][min_max_pods] / iterations_sec['runc'][min_max_pods]
        answer['Ratio iterations/CPU sec'] = iterations_cpu_sec['kata'][min_max_pods] / iterations_cpu_sec['runc'][min_max_pods]
        return answer
