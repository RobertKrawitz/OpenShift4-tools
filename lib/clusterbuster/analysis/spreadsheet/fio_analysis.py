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
Throughput (MB/sec)
Kata\trunc\tratio\tmin_ratio\tmax_ratio
"""
            answer += '\t'.join([self._prettyprint(data['throughput']['kata'][True] / 1000000, precision=3, base=0),
                                 self._prettyprint(data['throughput']['runc'][True] / 1000000, precision=3, base=0),
                                 self._prettyprint(data['throughput']['ratio'][True], precision=3, base=0),
                                 self._prettyprint(data['throughput']['min_ratio'][True], precision=3, base=0),
                                 self._prettyprint(data['throughput']['max_ratio'][True], precision=3, base=0)]) + "\n"
                                 
                                
            answer += """IO/sec
Kata\trunc\tratio\tmin_ratio\tmax_ratio
"""
            answer += '\t'.join([self._prettyprint(data['iops']['kata'][True], precision=3, base=0),
                                 self._prettyprint(data['iops']['runc'][True], precision=3, base=0),
                                 self._prettyprint(data['iops']['ratio'][True], precision=3, base=0),
                                 self._prettyprint(data['iops']['min_ratio'][True], precision=3, base=0),
                                 self._prettyprint(data['iops']['max_ratio'][True], precision=3, base=0)]) + "\n\n"
        else:
            answer = f"""{var}
Throughput (MB/sec)
{var.replace('By ', '')}\tKata\trunc\tratio\tmin_ratio\tmax_ratio
"""
            for value in data['throughput']['kata'].keys():
                answer += '\t'.join([str(value),
                                     self._prettyprint(data['throughput']['kata'][value] / 1000000, precision=3, base=0),
                                     self._prettyprint(data['throughput']['runc'][value] / 1000000, precision=3, base=0),
                                     self._prettyprint(data['throughput']['ratio'][value], precision=3, base=0),
                                     self._prettyprint(data['throughput']['min_ratio'][value], precision=3, base=0),
                                     self._prettyprint(data['throughput']['max_ratio'][value], precision=3, base=0)]) + "\n"
            answer += f"""
IO/sec
{var.replace('By ', '')}\tKata\trunc\tratio\tmin_ratio\tmax_ratio
"""
            for value in data['iops']['kata'].keys():
                answer += '\t'.join([str(value),
                                     self._prettyprint(data['iops']['kata'][value], precision=3, base=0),
                                     self._prettyprint(data['iops']['runc'][value], precision=3, base=0),
                                     self._prettyprint(data['iops']['ratio'][value], precision=3, base=0),
                                     self._prettyprint(data['iops']['min_ratio'][value], precision=3, base=0),
                                     self._prettyprint(data['iops']['max_ratio'][value], precision=3, base=0)]) + "\n"
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
