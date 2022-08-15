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

import sys
import importlib
import inspect


class ClusterBusterAnalyzeOne:
    def __init__(self, workload: str, data: dict, metadata: dict):
        self._workload = workload
        self._data = data
        self._metadata = metadata

    def _fformat(self, num: float, precision: float = 5):
        """
        Return a formatted version of a float.  If precision is 0, no decimal point is printed.
        :param num:
        :param precision:
        """
        try:
            if precision > 1:
                return f'{num:.{precision}f}'
            else:
                return int(round(num))
        except Exception:
            return num

    def _prettyprint(self, num: float, precision: float = 5, integer: bool = False, base: int = 1000, suffix: str = ''):
        """
        Return a pretty printed version of a float.
        Base 100:  print percent
        Base 1000: print with decimal units (1000, 1000000...)
        Base 1024: print with binary units (1024, 1048576...)
                   This only applies to values larger than 1;
                   smaller values are always printed with
                   decimal units
        Base 0:    do not use any units
        Base -1:   Only print units for <1
        :param num:
        :param precision:
        :param base: 0, 1000, 1024, or -1
        :param integer: print as integer
        :param suffix: trailing suffix (e. g. "B/sec")
        """
        if num is None:
            return 'None'
        try:
            num = float(num)
        except Exception:
            return str(num)
        if integer != 0 or num == 0:
            return str(int(num))
        elif base == 0:
            if suffix and suffix != '':
                return f'{self._fformat(num, precision=precision)} {suffix}'
            else:
                return f'{self._fformat(num, precision=precision)}'
        elif base == 100:
            return f'{self._fformat(num * 100, precision=precision)} %'
        elif base == 1000 or base == 10:
            infix = ''
            base = 1000
        elif base == 1024 or base == 2:
            infix = 'i'
            base = 1024
        elif base != -10 or base != -1 or base != -1000:
            raise(Exception(f'Illegal base {base} for prettyprint; must be 1000 or 1024'))
        if base > 0 and abs(num) >= base ** 5:
            return f'{self._fformat(num / (base ** 5), precision=precision)} P{infix}{suffix}'
        elif base > 0 and abs(num) >= base ** 4:
            return f'{self._fformat(num / (base ** 4), precision=precision)} T{infix}{suffix}'
        elif base > 0 and abs(num) >= base ** 3:
            return f'{self._fformat(num / (base ** 3), precision=precision)} G{infix}{suffix}'
        elif base > 0 and abs(num) >= base ** 2:
            return f'{self._fformat(num / (base ** 2), precision=precision)} M{infix}{suffix}'
        elif base > 0 and abs(num) >= base ** 1:
            return f'{self._fformat(num / base, precision=precision)} K{infix}{suffix}'
        elif abs(num) >= 1 or num == 0:
            if integer != 0 or num == 0:
                precision = 0
            return f'{self._fformat(num, precision=precision)} {suffix}'
        elif abs(num) >= 10 ** -3:
            return f'{self._fformat(num * (1000), precision=precision)} m{suffix}'
        elif abs(num) >= 10 ** -6:
            return f'{self._fformat(num * (1000 ** 2), precision=precision)} u{suffix}'
        elif abs(num) >= 10 ** -9:
            return f'{self._fformat(num * (1000 ** 3), precision=precision)} n{suffix}'
        else:
            return f'{self._fformat(num * (1000 ** 4), precision=precision)} p{suffix}'

    def _analyze_variables(self, data, columns, header: str, divisor = 1.0, valfunc = None, integer: bool=True, ratio: bool=True, difference: bool=False):
        if not isinstance(columns, list):
            columns = [columns]
        pcolumns = []
        for c in columns:
            if c is None:
                pcolumns.append('')
            else:
                pcolumns.append(c)

        column_separator = '\t\t'
        columns_out_base = 'kata\trunc'
        if ratio:
            columns_out_base += '\tratio'
            column_separator += '\t'
        if difference:
            columns_out_base += '\tdelta'
            column_separator += '\t'
        columns_out_1 = '# Pods\t' + column_separator.join(pcolumns)
        columns_out_2 = '# Pods\t' + '\t'.join([columns_out_base for c in pcolumns])

        answer = f"""
{header}, N pods
{columns_out_1}
{columns_out_2}
"""
        rows = []
        for pods, data1 in data.items():
            row = [str(pods)]
            for column in columns:
                if valfunc is not None:
                    runc_value = valfunc(data1, 'runc', column)
                    kata_value = valfunc(data1, 'kata', column)
                else:
                    if 'runc' in data1:
                        runc_value = data1['runc'][column] / divisor
                    else:
                        runc_value = None
                    if 'kata' in data1:
                        kata_value = data1['kata'][column] / divisor
                    else:
                        kata_value = None
                if kata_value:
                    row.append(self._prettyprint(kata_value, base=0, integer=integer))
                else:
                    row.append('')
                if runc_value:
                    row.append(self._prettyprint(runc_value, base=0, integer=integer))
                else:
                    row.append('')
                if runc_value is not None and kata_value is not None:
                    if ratio:
                        row.append(self._prettyprint(kata_value / runc_value, base=0, precision=3))
                    if difference:
                        row.append(self._prettyprint(kata_value - runc_value, base=0, integer=integer, precision=3))
            rows.append('\t'.join(row))
        return answer + '\n'.join(rows) + '\n'

    def Analyze(self):
        pass


class ClusterBusterAnalysis:
    """
    Analyze ClusterBuster reports
    """
    def __init__(self, data: dict, report_type=None):
        self._data = data
        if report_type is None:
            report_type = 'ci'
        self._report_type = report_type

    def Analyze(self):
        report = dict()
        metadata = dict()
        status = dict()
        report_type = None
        if 'metadata' in self._data:
            metadata = self._data['metadata']
        if 'status' in self._data:
            status = self._data['status']
            print(f'>>>>>> {metadata}', file=sys.stderr)
        for workload, workload_data in self._data.items():
            if workload == 'metadata' or workload == 'status':
                continue
            try:
                imported_lib = importlib.import_module(f'..{self._report_type}.{workload}_analysis', __name__)
            except Exception as exc:
                print(f'Warning: no analyzer for workload {workload} {exc}', file=sys.stderr)
                continue
            try:
                for i in inspect.getmembers(imported_lib):
                    if i[0] == f'{workload}_analysis':
                        report[workload] = i[1](workload, workload_data, metadata).Analyze()
                        if report_type is None:
                            report_type = type(report[workload])
                        elif report_type != type(report[workload]):
                            raise TypeError(f"Incompatible report types for {workload}: expect {report_type}, found {type(report[workload])}")
            except Exception as exc:
                raise(exc)
        if report_type == str:
            return '\n\n'.join([str(v) for v in report.values()])
        elif report_type == dict or report_type == list:
            report['metadata'] = dict()
            for v in ['uuid', 'run_host', 'openshift_version', 'kata_version']:
                if v in metadata:
                    report['metadata'][v] = metadata[v]
            for v in ['result', 'job_start', 'job_end', 'job_runtime']:
                if v in status:
                    report['metadata'][v] = status[v]
            if 'failed' in status and len(status['failed']) > 0:
                report['metadata']['failed'] = status['failed']
            print(f'>>>>>>>>>>>>>>>>>>> {report["metadata"]}', file=sys.stderr)
            return report
        else:
            raise TypeError(f"Unexpected report type {report_type}, expect either str or dict")
