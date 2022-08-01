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
Rate (MB/sec)\t\t\tLatency (usec)
Kata\trunc\tratio\tKata\trunc\tratio
"""
            answer += '\t'.join([self._prettyprint(data['kata']['rate'] / 1000000, precision=3, base=0),
                                 self._prettyprint(data['runc']['rate'] / 1000000, precision=3, base=0),
                                 self._prettyprint(data['ratio']['rate'], precision=3, base=0),
                                 self._prettyprint(1000000 * data['kata']['avg_time_op'], precision=3, base=0),
                                 self._prettyprint(1000000 * data['runc']['avg_time_op'], precision=3, base=0),
                                 self._prettyprint(data['ratio']['avg_time_op'], precision=3, base=0)]) + "\n"
            return answer + '\n'
        else:
            answer = f"""{var}
Value\tRate (MB/sec)\t\t\tLatency (usec)
\tKata\trunc\tratio\tKata\trunc\tratio
"""
            for value, vdata in data.items():
                answer += '\t'.join([str(value),
                                     self._prettyprint(vdata['kata']['rate'] / 1000000, precision=3, base=0),
                                     self._prettyprint(vdata['runc']['rate'] / 1000000, precision=3, base=0),
                                     self._prettyprint(vdata['ratio']['rate'], precision=3, base=0),
                                     self._prettyprint(1000000 * vdata['kata']['avg_time_op'], precision=3, base=0),
                                     self._prettyprint(1000000 * vdata['runc']['avg_time_op'], precision=3, base=0),
                                     self._prettyprint(vdata['ratio']['avg_time_op'], precision=3, base=0)]) + "\n"
            return answer + '\n'

    def Analyze(self):
        report = super().Analyze()
        answer = f"""Workload: {report['workload']}
uuid: {report['uuid']}

"""
        for var, data in report.items():
            if isinstance(data, dict):
                answer += self.analyze_one(var, data)
        return answer
