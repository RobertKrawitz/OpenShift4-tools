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


class SpreadsheetAnalysis(ClusterBusterAnalyzeSummaryGeneric):
    def __init__(self, workload: str, data: dict, metadata: dict, dimensions: list, variables: list, filters: dict=None):
        self._sp_dimensions = dimensions
        self._sp_variables = variables
        analysis_vars = [v['var'] for v in self._sp_variables]
        ClusterBusterAnalyzeSummaryGeneric.__init__(self, workload, data, metadata, dimensions, analysis_vars, filters=filters)

    def _analyze_one(self, dimension, data):
        answer = ""
        if dimension == 'Overall':
            answer += """Total
Metric\tKata\trunc
"""
            for v in self._sp_variables:
                var = v['var']
                name = v.get('name', var)
                multiplier = v.get('multiplier', 1)
                answer += '\t'.join([name,
                                     self._prettyprint(data[var]['kata'][True] * multiplier, precision=3, base=0),
                                     self._prettyprint(data[var]['runc'][True] * multiplier, precision=3, base=0)]) + "\n"
            answer += """
Total (Ratio)
Metric\tMin ratio\tAvg ratio\tMax ratio
"""
            for v in self._sp_variables:
                var = v['var']
                name = v.get('name', var)
                answer += '\t'.join([name,
                                     self._prettyprint(data[var]['min_ratio'][True] * multiplier, precision=3, base=0),
                                     self._prettyprint(data[var]['ratio'][True] * multiplier, precision=3, base=0),
                                     self._prettyprint(data[var]['max_ratio'][True] * multiplier, precision=3, base=0)]) + "\n"
        else:
            answer += dimension
            for v in self._sp_variables:
                var = v['var']
                name = v.get('name', var)
                unit = v.get('unit', '')
                multiplier = v.get('multiplier', 1)
                answer += f"""
{name}{unit}
{dimension.replace('By ', '')}\tKata\trunc
"""
                for value in data[var]['kata'].keys():
                    answer += '\t'.join([str(value),
                                         self._prettyprint(data[var]['kata'][value] * multiplier, precision=3, base=0),
                                         self._prettyprint(data[var]['runc'][value] * multiplier, precision=3, base=0)]) + "\n"
            for v in self._sp_variables:
                var = v['var']
                name = v.get('name', var)
                answer += f"""
{name} (Ratio)
{dimension.replace('By ', '')}\tMin ratio\tAvg ratio\tMax ratio
"""
                for value in data[var]['kata'].keys():
                    answer += '\t'.join([str(value),
                                         self._prettyprint(data[var]['min_ratio'][value], precision=3, base=0),
                                         self._prettyprint(data[var]['ratio'][value], precision=3, base=0),
                                         self._prettyprint(data[var]['max_ratio'][value], precision=3, base=0)]) + "\n"
        return answer + '\n\n'

    def Analyze(self, report_detail=True):
        report, detail = super().Analyze(report_detail=report_detail)
        answer = f"""Workload: {report['workload']}
uuid: {report['uuid']}

"""
        for var, data in report.items():
            if isinstance(data, dict):
                answer += self._analyze_one(var, data)
        detail_vars = []
        header1 = ''
        header2 = 'Case\t'
        for v in self._sp_variables:
            if v.get('detail', True):
                detail_vars.append(v)
                var = v['var']
                header1 += '\t' + v.get('name', var) + v.get('unit', '') + '\t\t'
                header2 += '\tKata\trunc\tratio'
        if len(detail_vars) >= 1:
            answer += f"""
{header1}
{header2}
"""
            for case, row in detail.items():
                answer += case
                for v in detail_vars:
                    var = v['var']
                    multiplier = v.get('multiplier', 1)
                    for rt in ['kata', 'runc']:
                        answer += '\t' + self._prettyprint(row[var][rt] * multiplier, precision=3, base=0)
                    answer += '\t' + self._prettyprint(row[var]['ratio'], precision=3, base=0)
                answer += '\n'
        return answer
