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


class fio_analysis(ClusterBusterAnalyzeSummaryGeneric):
    """
    Analyze fio data
    """

    def __init__(self, workload: str, data: dict, metadata: dict):
        dimensions = ['By Pod Count', 'By Engine', 'By I/O Depth', '-By Fdatasync', '-By Direct', 'By Operation', 'By Blocksize']
        variables = ['throughput', 'iops']
        filters = {
            'By Direct': self.__filter_direct
            }
        ClusterBusterAnalyzeSummaryGeneric.__init__(self, workload, data, metadata, dimensions, variables, filters=filters)

    def __filter_direct(self, dimension, value):
        return value != 0

    def _retrieve_datum(self, var: str, value: dict):
        return value['total'].get(var, 0)

    def analyze_one(self, var, data):
        if var == 'Overall':
            answer = """Total
Throughput (MB/sec)\t\t\tIO/sec
Kata\trunc\tratio\tKata\trunc\tratio
"""
            answer += '\t'.join([self._prettyprint(data['kata']['throughput'] / 1000000, precision=3, base=0),
                                 self._prettyprint(data['runc']['throughput'] / 1000000, precision=3, base=0),
                                 self._prettyprint(data['ratio']['throughput'], precision=3, base=0),
                                 self._prettyprint(data['kata']['iops'], precision=3, base=0),
                                 self._prettyprint(data['runc']['iops'], precision=3, base=0),
                                 self._prettyprint(data['ratio']['iops'], precision=3, base=0)]) + "\n"
            return answer + '\n'
        else:
            answer = f"""{var}
Value\tThroughput (MB/sec)\t\t\tIO/sec
\tKata\trunc\tratio\tKata\trunc\tratio
"""
            for value, vdata in data.items():
                answer += '\t'.join([str(value),
                                     self._prettyprint(vdata['kata']['throughput'] / 1000000, precision=3, base=0),
                                     self._prettyprint(vdata['runc']['throughput'] / 1000000, precision=3, base=0),
                                     self._prettyprint(vdata['ratio']['throughput'], precision=3, base=0),
                                     self._prettyprint(vdata['kata']['iops'], precision=3, base=0),
                                     self._prettyprint(vdata['runc']['iops'], precision=3, base=0),
                                     self._prettyprint(vdata['ratio']['iops'], precision=3, base=0)]) + "\n"
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
