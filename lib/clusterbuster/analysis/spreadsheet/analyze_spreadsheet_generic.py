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
import re


class SpreadsheetAnalysis(ClusterBusterAnalyzeSummaryGeneric):
    def __init__(self, workload: str, data: dict, metadata: dict, dimensions: list, variables: list, filters: dict = None):
        self._runs = metadata['jobs'].keys()
        self._baseline = metadata['baseline']
        self._sp_dimensions = dimensions
        self._sp_variables = variables
        analysis_vars = [v['var'] for v in self._sp_variables]
        ClusterBusterAnalyzeSummaryGeneric.__init__(self, workload, data, metadata, dimensions, analysis_vars, filters=filters)

    def print_safe(self, data: dict, d1, d2, multiplier: float = 1, print_empty: bool = False):
        try:
            val = data[d1][d2]
            return self._prettyprint(val * multiplier, precision=3, base=0)
        except Exception:
            return '' if print_empty else 'N/A'

    def _get_all_keys(self, data):
        value_hash = {}
        for run in data:
            for key in data[run].keys():
                value_hash[key] = 1
        return sorted(value_hash.keys())

    def _supports_variable(self, v, data):
        for key in self._get_all_keys(data):
            if v in data:
                return True
        return False

    def _supported_variables(self, data):
        answer = []
        for v in self._sp_variables:
            for key in self._get_all_keys(data):
                if v['var'] in data.keys():
                    answer.append(v['var'])
                    break
        return answer

    def _analyze_one_generic(self, dimension, data):
        tab = '\t'
        if dimension == 'Overall':
            answer = "Total:"
            run_names = data[list(data.keys())[0]].keys()
            for metric in "value", "ratio", "max_ratio", "min_ratio":
                answer += f"""
{metric}{tab}{tab.join(run_names)}
"""
                has_data_metric = True
                for vn, v_data in data.items():
                    has_data = False
                    for run in v_data.values():
                        if metric in run["Total"]:
                            has_data = True
                            has_data_metric = True
                            break
                    if not has_data:
                        continue
                    runs = v_data.keys()
                    for v in self._sp_variables:
                        if v['var'] == vn:
                            break
                    name = v.get('name', vn)
                    if metric == 'value':
                        unit = v.get('unit', '')
                        multiplier = v.get('multiplier', 1)
                        answer += f'{name}{unit}{tab}'
                        answer += tab.join([self._prettyprint(run['Total'].get(metric, '') * multiplier, precision=3, base=0) for run in v_data.values()])
                    else:
                        answer += f'{name}{tab}'
                        answer += tab.join([self._prettyprint(run['Total'].get(metric, ''), precision=3, base=0) for run in v_data.values()])
                    answer += "\n"
                answer += "\n"
            if has_data_metric:
                return answer
            else:
                return ''
        else:
            answer = f'{dimension}:'
            for v in self._sp_variables:
                answers = []
                vn = v['var']
                if not self._supports_variable(vn, data):
                    continue
                var = data[vn]
                name = v.get('name', vn)
                unit = v.get('unit', '')
                multiplier = v.get('multiplier', 1)
                dim_name = dimension.replace('By ', '')
                runs = data[vn].keys()
                report_answer = f"""
Operation: {name}{unit}
{dim_name}{tab}{tab.join(runs)}
"""
                for key in self._get_all_keys(var):
                    report_answer += f'{key}{tab}'
                    report_answer += tab.join([self._prettyprint(var[run][key]["value"] * multiplier, precision=3, base=0) if key in var[run] and 'value' in var[run][key] else '' for run in runs]) + '\n'
                answers.append(report_answer)
                for op in 'ratio', 'min_ratio', 'max_ratio':
                    report_answer = f"{op} {tab.join(runs)}" + '\n'
                    have_data = False
                    for key in self._get_all_keys(var):
                        report_line = tab.join([self._prettyprint(var[run][key][op], precision=3, base=0) if key in var[run] and op in var[run][key] else '' for run in runs])
                        if re.search(report_line, r'[0-9]'):
                            have_data = True
                            report_answer += f'{key}{tab}{report_line}' + '\n'
                    if have_data:
                        answers.append(report_answer)
            answer += '\n'.join(answers)
            return answer + '\n\n'

    def Analyze(self, report_detail=True):
        report, detail = super().Analyze(report_detail=report_detail)
        answer = f"""Workload: {report['workload']}

"""
        for var, data in report.items():
            if isinstance(data, dict):
                answer += self._analyze_one_generic(var, data)
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
