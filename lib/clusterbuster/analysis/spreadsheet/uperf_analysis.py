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

from ..summary.analyze_generic import ClusterBusterAnalyzeSummaryGeneric


class uperf_analysis(ClusterBusterAnalyzeSummaryGeneric):
    """
    Analyze uperf data
    """

    def __init__(self, workload: str, data: dict, metadata: dict):
        dimensions = ['By Pod Count', 'By Message Size', 'By Threads']
        variables = ['rate', 'avg_time_op']
        ClusterBusterAnalyzeSummaryGeneric.__init__(self, workload, data, metadata, dimensions, variables)

    def analyze_one(self, var, data):
        if var == 'Overall':
            answer = """Total
Metric\tKata\trunc
"""
            answer += '\t'.join(['Rate (MB/sec)',
                                 self._prettyprint(data['rate']['kata'][True] / 1000000, precision=3, base=0),
                                 self._prettyprint(data['rate']['runc'][True] / 1000000, precision=3, base=0)]) + "\n"
            answer += '\t'.join(['Latency (usec)',
                                 self._prettyprint(1000000 * data['avg_time_op']['kata'][True], precision=3, base=0),
                                 self._prettyprint(1000000 * data['avg_time_op']['runc'][True], precision=3, base=0)]) + "\n\n"
            answer += """Ratio
Min ratio\tAvg ratio\tMax ratio
"""
            answer += '\t'.join(['Rate',
                                 self._prettyprint(data['rate']['min_ratio'][True], precision=3, base=0),
                                 self._prettyprint(data['rate']['ratio'][True], precision=3, base=0),
                                 self._prettyprint(data['rate']['max_ratio'][True], precision=3, base=0)]) + "\n"
            answer += '\t'.join(['Latency',
                                 self._prettyprint(data['avg_time_op']['min_ratio'][True], precision=3, base=0),
                                 self._prettyprint(data['avg_time_op']['ratio'][True], precision=3, base=0),
                                 self._prettyprint(data['avg_time_op']['max_ratio'][True], precision=3, base=0)]) + "\n\n"
            answer + '\n\n'
        else:
            answer = f"""{var}
Rate (MB/sec)
{var.replace('By ', '')}\tKata\trunc
"""
            for value in data['rate']['kata'].keys():
                answer += '\t'.join([str(value),
                                     self._prettyprint(data['rate']['kata'][value] / 1000000, precision=3, base=0),
                                     self._prettyprint(data['rate']['runc'][value] / 1000000, precision=3, base=0)]) + "\n"
            answer += f"""
Latency (usec)
{var.replace('By ', '')}\tKata\trunc
"""
            for value in data['avg_time_op']['kata'].keys():
                answer += '\t'.join([str(value),
                                     self._prettyprint(1000000 * data['avg_time_op']['kata'][value], precision=3, base=0),
                                     self._prettyprint(1000000 * data['avg_time_op']['runc'][value], precision=3, base=0)]) + "\n"
            answer += f"""
Rate (Ratio)
{var.replace('By ', '')}\tMin ratio\tAvg ratio\tMax ratio
"""
            for value in data['rate']['kata'].keys():
                answer += '\t'.join([str(value),
                                     self._prettyprint(data['rate']['min_ratio'][value], precision=3, base=0),
                                     self._prettyprint(data['rate']['ratio'][value], precision=3, base=0),
                                     self._prettyprint(data['rate']['max_ratio'][value], precision=3, base=0)]) + "\n"
            answer += f"""
Latency (Ratio)
{var.replace('By ', '')}\tMin ratio\tAvg ratio\tMax ratio
"""
            for value in data['avg_time_op']['kata'].keys():
                answer += '\t'.join([str(value),
                                     self._prettyprint(data['avg_time_op']['min_ratio'][value], precision=3, base=0),
                                     self._prettyprint(data['avg_time_op']['ratio'][value], precision=3, base=0),
                                     self._prettyprint(data['avg_time_op']['max_ratio'][value], precision=3, base=0)]) + "\n"
        return answer + '\n\n'

    def Analyze(self):
        report = super().Analyze()
        answer = f"""Workload: {report['workload']}
uuid: {report['uuid']}

"""
        for var, data in report.items():
            if isinstance(data, dict):
                answer += self.analyze_one(var, data)
        return answer
