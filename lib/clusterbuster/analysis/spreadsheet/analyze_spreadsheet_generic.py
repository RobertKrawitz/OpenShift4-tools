#!/usr/bin/env python3
# Copyright 2022-2023 Robert Krawitz/Red Hat
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
    def __init__(self, workload: str, data: dict, metadata: dict, dimensions: list,
                 variables: list, filters: dict = None):
        self._baseline = metadata['baseline']
        self._sp_dimensions = dimensions
        self._sp_variables = variables
        analysis_vars = [v['var'] for v in self._sp_variables]
        super().__init__(workload, data, metadata, dimensions, analysis_vars, filters=filters)

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

    def _get_run_data(self, v_data, key, metric):
        return [self._safe_get(v_data, [run, key, metric], '') for run in self._runs]

    def _analyze_one_generic(self, dimension, data):
        tab = '\t'
        if dimension == 'Overall':
            answer = "Total:"
            for metric in "value", "ratio", "max_ratio", "min_ratio":
                answer += f"""
{metric}{tab}{tab.join(self._runs)}
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
                    for v in self._sp_variables:
                        if v['var'] == vn:
                            break
                    name = v.get('name', vn)
                    if metric == 'value':
                        unit = v.get('unit', '')
                        multiplier = v.get('multiplier', 1)
                        base = v.get('base', None)
                        answer += f'{name}{unit}{tab}'
                        answer += tab.join([self._prettyprint(datum, multiplier=multiplier, base=base)
                                            for datum in self._get_run_data(v_data, 'Total', metric)])
                    else:
                        answer += f'{name}{tab}'
                        answer += tab.join([self._prettyprint(datum, precision=3, base=0)
                                            for datum in self._get_run_data(v_data, 'Total', metric)])
                    answer += "\n"
                answer += "\n"
            if has_data_metric:
                return answer
            else:
                return ''
        else:
            answer = f'{dimension}:'
            answers = []
            for v in self._sp_variables:
                vn = v['var']
                if vn not in data:
                    continue
                var = data[vn]
                name = v.get('name', vn)
                unit = v.get('unit', '')
                multiplier = v.get('multiplier', 1)
                base = v.get('base', None)
                dim_name = dimension.replace('By ', '')
                report_answer = f"""
Operation: {name}{unit}
{dim_name}{tab}{tab.join(self._runs)}
"""
                for key in self._get_all_keys(var):
                    report_answer += f'{key}{tab}'
                    report_answer += tab.join([self._prettyprint(datum, multiplier=multiplier, base=base)
                                               for datum in self._get_run_data(var, key, "value")]) + '\n'
                answers.append(report_answer)
                for op in 'ratio', 'min_ratio', 'max_ratio':
                    report_answer = f"{op} {tab.join(self._runs)}" + '\n'
                    have_data = False
                    for key in self._get_all_keys(var):
                        report_line = tab.join([self._prettyprint(datum, precision=3, base=0)
                                                for datum in self._get_run_data(var, key, op)]) + '\n'
                        if re.search(report_line, r'[0-9]'):
                            have_data = True
                            report_answer += f'{key}{tab}{report_line}' + '\n'
                    if have_data:
                        answers.append(report_answer)
            answer += '\n'.join(answers)
            return answer + '\n\n'

    def _print_safe(self, data: dict, d1, d2, d3, multiplier: float = 1):
        try:
            val = self._safe_get(data, [d1, d2, d3])
            return self._prettyprint(val * multiplier, precision=3, base=0)
        except Exception:
            return ''

    def Analyze(self, report_detail=True):
        report, detail = super().Analyze(report_detail=report_detail)
        answer = f"""Workload: {report['workload']}

"""
        tab = '\t'
        for var, data in report.items():
            if isinstance(data, dict):
                answer += self._analyze_one_generic(var, data)
        answer += '\nMetric\tCase\t' + '\t'.join(self._runs) + '\n'
        for v in self._sp_variables:
            vn = v['var']
            if vn not in data:
                continue
            var = data[vn]
            name = v.get('name', vn)
            unit = v.get('unit', '')
            multiplier = v.get('multiplier', 1)
            answer += f'{name}{unit}'
            for case, row in detail.items():
                answer += f'{tab}{case}'
                for run in self._runs:
                    answer += '\t' + self._print_safe(row, vn, run, "value", multiplier)
                answer += '\n'
            answer += '\n'
        return answer
