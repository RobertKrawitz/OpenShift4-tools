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
    def __init__(self, workload: str, data: dict, metadata: dict, dimensions: list, variables: list, filters: dict = None):
        self._sp_dimensions = dimensions
        self._sp_variables = variables
        analysis_vars = [v['var'] for v in self._sp_variables]
        ClusterBusterAnalyzeSummaryGeneric.__init__(self, workload, data, metadata, dimensions, analysis_vars, filters=filters)

    def print_safe(self, data: dict, d1, d2, multiplier: float = 1):
        try:
            val = data[d1][d2]
            return self._prettyprint(val * multiplier, precision=3, base=0)
        except Exception:
            return 'N/A'

    def __analyze_one_runc_only(self, dimension, data):
        answer = ""
        if dimension == 'Overall':
            answer += """Total
Metric\tvalue
"""
            for v in self._sp_variables:
                var = v['var']
                name = v.get('name', var)
                multiplier = v.get('multiplier', 1)
                answer += '\t'.join([name,
                                     self.print_safe(data[var], 'runc', True, multiplier)]) + "\n"
        else:
            answer += dimension
            for v in self._sp_variables:
                var = v['var']
                name = v.get('name', var)
                unit = v.get('unit', '')
                multiplier = v.get('multiplier', 1)
                answer += f"""
{name}{unit}
{dimension.replace('By ', '')}\tvalue
"""
                for value in data[var]['runc'].keys():
                    answer += '\t'.join([str(value),
                                         self.print_safe(data[var], 'runc', value, multiplier)]) + "\n"
        return answer + '\n\n'

    def __analyze_one_kata(self, dimension, data):
        answer = ""
        if dimension == 'Overall':
            answer += """Total
Metric\tKata\trunc\tratio
"""
            for v in self._sp_variables:
                var = v['var']
                name = v.get('name', var)
                multiplier = v.get('multiplier', 1)
                answer += '\t'.join([name,
                                     self.print_safe(data[var], 'kata', True, multiplier),
                                     self.print_safe(data[var], 'runc', True, multiplier),
                                     self.print_safe(data[var], 'ratio', True)]) + "\n"
            answer += """
Total (Ratio)
Metric\tMin ratio\tAvg ratio\tMax ratio
"""
            for v in self._sp_variables:
                var = v['var']
                name = v.get('name', var)
                answer += '\t'.join([name,
                                     self.print_safe(data[var], 'min_ratio', True),
                                     self.print_safe(data[var], 'ratio', True),
                                     self.print_safe(data[var], 'max_ratio', True)]) + "\n"
        else:
            answer += dimension
            for v in self._sp_variables:
                var = v['var']
                name = v.get('name', var)
                unit = v.get('unit', '')
                multiplier = v.get('multiplier', 1)
                answer += f"""
{name}{unit}
{dimension.replace('By ', '')}\tKata\trunc\tratio
"""
                if 'kata' in data[var]:
                    for value in data[var]['kata'].keys():
                        answer += '\t'.join([str(value),
                                             self.print_safe(data[var], 'kata', value, multiplier),
                                             self.print_safe(data[var], 'runc', value, multiplier),
                                             self.print_safe(data[var], 'ratio', value)]) + "\n"
            for v in self._sp_variables:
                var = v['var']
                name = v.get('name', var)
                answer += f"""
{name} (Ratio)
{dimension.replace('By ', '')}\tMin ratio\tAvg ratio\tMax ratio
"""
                if 'kata' in data[var]:
                    for value in data[var]['kata'].keys():
                        answer += '\t'.join([str(value),
                                             self.print_safe(data[var], 'min_ratio', value),
                                             self.print_safe(data[var], 'ratio', value),
                                             self.print_safe(data[var], 'max_ratio', value)]) + "\n"
        return answer + '\n\n'

    def _analyze_one(self, dimension, data):
        for v in self._sp_variables:
            if 'kata' in data[v['var']]:
                return self.__analyze_one_kata(dimension, data)
        return self.__analyze_one_runc_only(dimension, data)

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
                        answer += '\t' + self.print_safe(row, var, rt, multiplier)
                    answer += '\t' + self.print_safe(row, var, 'ratio')
                answer += '\n'
        return answer
