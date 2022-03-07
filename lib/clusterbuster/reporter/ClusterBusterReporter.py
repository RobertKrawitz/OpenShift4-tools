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

import json
import sys
import textwrap
from copy import deepcopy


class ClusterBusterReporter:
    """
    Report generator for ClusterBuster
    """

    def __init__(self, jdata: dict, report_format: str, indent: int = 2, report_width=78):
        """
        Initializer for generic ClusterBuster report
        :param jdata: JSON data to report
        :param report_format: Report format, one of json-summary, json, json-verbose, verbose, summary
        :param indent: Per-level indentation
        :param report_width: Width of the report
        """
        self._jdata = deepcopy(jdata)
        self._format = report_format
        self._all_clients_are_on_the_same_node = self.__are_clients_all_on_same_node()
        self._summary = {'cpu_time': 0,
                         'runtime': 0,
                         'total_instances': 0}
        self._rows = []
        self._timeline_vars = []
        self._accumulator_vars = []
        self._summary_indent = indent
        self._report_width = report_width
        self._verbose_indent = 0
        self._header_keys = {}
        self._fields_to_copy = []
        self._add_timeline_vars(['data_start', 'data_end', 'pod_start', 'pod_create'])
        self._add_accumulators(['user_cpu_time', 'system_cpu_time', 'cpu_time', 'data_elapsed_time'])

    def create_report(self, outfile=sys.stdout):
        """
        Create a report
        """
        if 'Results' in self._jdata:
            rows = self._jdata['Results']
        else:
            rows = []
        for row in rows:
            self._create_row(row)

        if len(rows) > 0:
            self._add_summary()

        if self._format == 'json-summary':
            answer = {
                'summary': self._summary,
                'metadata': self._jdata['metadata'],
                }
            json.dump(answer, sys.stdout, sort_keys=True, indent=4)
        elif self._format == 'json':
            answer = {
                'summary': self._summary,
                'metadata': self._jdata['metadata'],
                'rows': self._rows
                }
            json.dump(answer, sys.stdout, sort_keys=True, indent=4)
        elif self._format == 'json-verbose':
            answer = deepcopy(self._jdata)
            answer['processed_results'] = {
                'summary': self._summary,
                'rows': self._rows
                }
            json.dump(answer, sys.stdout, sort_keys=True, indent=4)
        else:
            self.__create_text_report(outfile=outfile)

    def _generate_summary(self, results: dict):
        """
        Generate summary results.  If a subclass wishes to override this to generate
        its own data, it must call this explicitly prior to generating its own results.

        :param results: Summary results that are updated
        """
        results['Total Clients'] = self._summary['total_instances']
        results['Elapsed Time Average'] = f"{self._summary['elapsed_time_average']:.{3}f}"
        results['Pod creation interval'] = f"{self._summary['pod_create_interval']:.5f}"
        results['Average pods created/sec'] = self._safe_div(self._summary['total_instances'],
                                                           (self._summary['last_pod_create'] -
                                                            self._summary['first_pod_create']),
                                                           precision=3, as_string=True)
        results['User CPU seconds'] = f"{self._summary['user_cpu_time']:.3f}"
        results['System CPU seconds'] = f"{self._summary['system_cpu_time']:.3f}"
        results['CPU seconds'] = f"{self._summary['cpu_time']:.3f}"
        start_time_uncertainty = None
        if 'controller_first_start_timestamp' in self._jdata['metadata']:
            start_time_offset = (self._jdata['metadata']['cluster_start_timestamp'] -
                                 self._jdata['metadata']['controller_second_start_timestamp'])
            start_time_uncertainty = (self._jdata['metadata']['controller_second_start_timestamp'] -
                                      self._jdata['metadata']['controller_first_start_timestamp'])
        else:
            start_time_offset = self._summary['first_pod_start']
        for var in self._timeline_vars:
            self.__normalize_timeline_val(var, self._summary, start_time_offset)
        results['Start time offset'] = f"{start_time_offset:.3f}"
        if start_time_uncertainty is not None:
            results['Start time uncertainty'] = f"{start_time_uncertainty:.3f}"
        if self._all_clients_are_on_the_same_node:
            results['CPU utilization'] = self._safe_div(self._summary['cpu_time'],
                                                        self._summary['data_run_interval'], 5, as_string=True)
            results['First pod start'] = f"{self._summary['first_pod_start']:.3f}"
            results['Last pod start'] = f"{self._summary['last_pod_start']:.3f}"
            results['Pod start interval'] = f"{self._summary['pod_start_interval']:.5f}"
            results['Average pods start/sec'] = self._safe_div(self._summary['total_instances'],
                                                               (self._summary['last_pod_start'] -
                                                                self._summary['first_pod_start']),
                                                               precision=3, as_string=True)
            results['First run start'] = f"{self._summary['first_data_start']:.3f}"
            results['Last run start'] = f"{self._summary['last_data_start']:.3f}"
            results['Run start interval'] = f"{self._summary['data_start_interval']:.5f}"
            results['Synchronization error'] = f"{self._summary['overlap_error']:.5f}"
            results['First run end'] = f"{self._summary['first_data_end']:.3f}"
            results['Last run end'] = f"{self._summary['last_data_end']:.3f}"
            results['Net elapsed time'] = f"{self._summary['data_run_interval']:.3f}"

    def _generate_row(self, results, row: dict):
        """
        Generate row results.  If a subclass wishes to override this to generate
        its own summary, it must call this explicitly prior to generating its own results.

        :param results: Output row results that are updated
        :param row: Input row
        """
        pass

    def _create_row(self, row: dict):
        """
        Create one output row.  If a subclass wishes to override this for its own
        custom processing, it should call this explicitly prior to generating
        its own results.

        :param row: Input row
        :return: Index of row in self._rows.  This is returned to allow subclasses
                 to determine what to update.

        """
        rowhash = {}
        rowhash['namespace'] = row['namespace']
        rowhash['pod'] = row['pod']
        rowhash['container'] = row['container']
        rowhash['node'] = self.__find_node_for_pod(namespace=row['namespace'], pod=row['pod'])
        rowhash['process_id'] = row['process_id']
        self._summary['total_instances'] += 1
        for var in self._timeline_vars:
            self.__update_timeline_val(var, row, self._summary)
        for accumulator in self._accumulator_vars:
            self.__update_accumulator_val(accumulator, row, self._summary, rowhash)
        for field_to_copy in self._fields_to_copy:
            self.__copy_field(field_to_copy, row, rowhash)

        self._rows.append(rowhash)
        return len(self._rows)-1

    def _add_summary(self):
        """
        Add summary information that can only be computed at the end.
        This is mostly for timeline variables.
        """
        self._summary['elapsed_time_average'] = self._safe_div(self._summary['data_elapsed_time'], self._summary['total_instances'])
        self._summary['pod_create_interval'] = self._summary['last_pod_create'] - self._summary['first_pod_create']
        if self._all_clients_are_on_the_same_node:
            self._summary['data_run_interval'] = self._summary['last_data_end'] - self._summary['first_data_start']
            self._summary['pod_start_interval'] = self._summary['last_pod_start'] - self._summary['first_pod_start']
            self._summary['data_start_interval'] = self._summary['last_data_start'] - self._summary['first_data_start']
            self._summary['data_end_interval'] = self._summary['last_data_end'] - self._summary['first_data_end']
            self._summary['overlap_error'] = self._safe_div(((self._summary['data_start_interval'] +
                                                              self._summary['data_end_interval']) / 2),
                                                            self._summary['elapsed_time_average'])
        else:
            self._summary['data_run_interval'] = self._summary['elapsed_time_average']

    def _add_timeline_vars(self, vars_to_update: list):
        """
        Add report variables of type timeline (e. g. absolute start
        and end times).  These are combined to determine absolute
        start and finish of various operations, and compute synchronization
        errors, for summarization

        All timeline variables are expected to have a suffix '_time_offset_from_base'.
        first_<var> and last_<var> names are synthesized in the summary.

        Variables may be dotted components, in which case they are extracted
        from the JSON structure.

        Variables in this list that are not present in the output are ignored.

        :param vars_to_update: List of variables to add
        """
        self._timeline_vars.extend(vars_to_update)

    def _add_accumulators(self, accumulators: list):
        """
        Add report variables that are accumulated, with max, min,
        square, and counter variables synthesized.  These are used in
        the summary and copied into rows.

        Variables may be dotted components, in which case they are extracted
        from the JSON structure.

        Variables in this list that are not present in the output are ignored.

        :param vars_to_update: List of variables to add
        """
        self._accumulator_vars.extend(accumulators)

    def _add_fields_to_copy(self, fields_to_copy: list):
        """
        Add report variables that are copied into result rows.

        Variables may be dotted components, in which case they are extracted
        from the JSON structure.

        Variables in this list that are not present in the output are ignored.

        :param vars_to_update: List of variables to add
        """
        self._fields_to_copy = fields_to_copy

    def _set_header_components(self, headers: list):
        """
        Set the list of header names that are used in the detail
        report, by level.

        :param headers: List of header names by depth.
        """
        self._header_keys['Detail'] = headers

    def _set_summary_header_components(self, headers: list):
        """
        Set the list of header names that are used in the summary
        report, by level.

        :param headers: List of header names by depth.
        """
        self._header_keys['Summary'] = headers

    def _fformat(self, num: float, precision: float = 5):
        """
        Return a formatted version of a float.  If precision is 0, no decimal point is printed.
        :param num:
        :param precision:
        """
        if precision > 1:
            return f'{num:.{precision}f}'
        else:
            return int(round(num))

    def _safe_div(self, num: float, denom: float, precision: int = None, as_string: bool = False):
        """
        Safely divide two numbers.  Return 'N/A' if denominator is zero.
        :param num: Numerator
        :param denom: Denominator
        :param precision: Precision to round the result
        :param as_string: If true, return value as strong
        """
        try:
            result = float(num) / float(denom)
            if precision is None:
                return result
            elif precision == 0:
                return int(round(result, 0))
            elif as_string:
                return self._fformat(result, precision)
            else:
                return round(result, precision)
        except Exception as exc:
            return 'N/A'

    def _wrap_text(self, text: str):
        """
        Wrap and indent text appropriately for reporting.
        This should not be used for multi-line strings.
        :param text: String to wrap
        :return: Filled string
        """
        return textwrap.fill(text, width=self._report_width, subsequent_indent='  ',
                             break_long_words=False, break_on_hyphens=False)

    def _insert_into(self, results: dict, path: list, value):
        """
        Insert value into results at location specified by path,
        creating missing keys as needed.
        :param results: Dictionary into which value should be inserted
        :param path: Path within directory where data should be inserted
        :param value: What should be inserted
        """

        results1 = results
        while len(path) > 1:
            key = path.pop(0)
            if key not in results1:
                results1[key] = {}
            results1 = results1[key]
        results1[key] = value

    def __are_clients_all_on_same_node(self):
        """
        Determine whether all clients ran on the same node.  This is used to determine
        whether items sensitive to exact time of day should be reported; if they are on
        different nodes whose times may be out of synchronization, these items should
        not be reported.
        :return:
        """
        node = None
        for obj in self._jdata['api_objects']:
            if obj['kind'] == 'Pod' and 'clusterbuster-client' in obj['labels'] and obj['labels']['clusterbuster-client']:
                if not node:
                    node = obj['nodeName']
                elif obj['nodeName'] != node:
                    return False
        return True

    def __find_node_for_pod(self, namespace: str, pod: str):
        """
        Find the node on which the pod under examination ran by searching JSON data.
        :param namespace: Namespace of the pod.
        :param pod: Name of the pod.
        :return:
        """
        for obj in self._jdata['api_objects']:
            if obj['kind'] == 'Pod' and obj['namespace'] == namespace and obj['name'] == pod:
                return obj['nodeName']
        return None

    def __row_name(self, row: dict):
        """
        Synthesize a row name for purpose of sorting.

        :param row:
        :return: Row name suitable for sorting.
        """
        return f'{row["namespace"]}~{row["pod"]}~{row["container"]}~{row.get("process_id", 0):#07d}'

    def __copy_field(self, var: str, row, rowhash: dict):
        """
        Copy one field from an input row to an output row.  This recurses for deep copy.
        :param var: Name of variable to copy
        :param row: Input row from JSON
        :param rowhash: Output row
        """
        components = var.split('.', 1)
        if len(components) > 1:
            if components[0] not in row:
                return
            if (isinstance(row[components[0]], list)):
                for element in row[components[0]]:
                    self.__copy_field(components[1], element, rowhash)
            else:
                if components[0] not in rowhash:
                    rowhash[components[0]] = {}
                self.__copy_field(components[1], row[components[0]], rowhash[components[0]])

        if len(components) > 1:
            if components[0] not in rowhash:
                [components[0]] = {}
            self.__copy_field(components[1], row[components[0]], rowhash[components[0]])
        else:
            rowhash[var] = row[var]

    def __update_timeline_val(self, var: str, row, summary: dict):
        """
        Update one summary timeline value.  This recurses for deep copy.
        :param var: Name of variable to update
        :param row: Input row from JSON
        :param summary: Summary of report
        """
        components = var.split('.', 1)
        if len(components) > 1:
            if components[0] not in row:
                return
            if (isinstance(row[components[0]], list)):
                for element in row[components[0]]:
                    self.__update_timeline_val(components[1], element, summary)
            else:
                if components[0] not in summary:
                    summary[components[0]] = {}
                self.__update_timeline_val(components[1], row[components[0]], summary[components[0]])
        else:
            row_val = row[f'{var}_time_offset_from_base']
            if f'first_{var}' not in summary or row_val < summary[f'first_{var}']:
                summary[f'first_{var}'] = row_val
            if f'last_{var}' not in summary or row_val > summary[f'last_{var}']:
                summary[f'last_{var}'] = row_val

    def __normalize_timeline_val(self, var: str, summary: dict, offset: float):
        """
        Normalize a timeline variable to the initial offset between host and pod
        :param var: Name of variable to update
        :param summary: Summary of report
        :param offset: Starting time offset
        """
        components = var.split('.', 1)
        if len(components) > 1:
            self.__normalize_timeline_val(components[1], summary[components[0]], offset)
        else:
            summary[f'first_{var}'] -= offset
            summary[f'last_{var}'] -= offset

    def __update_accumulator_val(self, var: str, row, summary, rowhash: dict):
        """
        Update one accumulator value.  This recurses for deep copy.
        :param var: Name of variable to update
        :param row: Input row from JSON
        :param rowhash: Output row
        :param summary: Summary of report
        """
        components = var.split('.', 1)
        if len(components) > 1:
            if components[0] not in row:
                return
            if (isinstance(row[components[0]], list)):
                for element in row[components[0]]:
                    self.__update_accumulator_val(components[1], element, summary, rowhash)
            else:
                if components[0] not in summary:
                    summary[components[0]] = {}
                if components[0] not in rowhash:
                    rowhash[components[0]] = {}
                self.__update_accumulator_val(components[1], row[components[0]], summary[components[0]], rowhash[components[0]])
        else:
            if var not in row:
                return
            row_val = row[var]
            if var not in summary:
                summary[var] = 0
            if f'{var}_counter' not in summary:
                summary[f'{var}_counter'] = 0
            if f'{var}_sq' not in summary:
                summary[f'{var}_sq'] = 0
            if f'max_{var}' not in summary:
                summary[f'max_{var}'] = row_val
                summary[f'min_{var}'] = row_val
            else:
                if (row_val > summary[f'max_{var}']):
                    summary[f'max_{var}'] = row_val
                if (row_val < summary[f'min_{var}']):
                    summary[f'min_{var}'] = row_val
            summary[var] += row_val
            summary[f'{var}_counter'] += 1
            summary[f'{var}_sq'] += row_val * row_val
            rowhash[var] = row_val

    def __compute_report_width(self, results: dict, indentation: int = None):
        """
        Compute recursively column widths for keys (taking into account indentation)
        and the integer part of floats.

        :param results: Results to be scanned
        :param indentation: Desired per-level indentation (default per the class)
        :return width: (maximum) width for the key field
        :return integer_width: (maximum) width for the integer component of any numbers
                               Strings are treated as having zero integer width,
                               but this value is used to determine string indentation
                               so that if possible strings are right aligned with
                               integers
        """
        width = 0
        integer_width = 0
        if indentation is None:
            indentation = self._summary_indent
        for key in results:
            if isinstance(results[key], dict):
                fwidth, nwidth = self.__compute_report_width(results[key], indentation=indentation)
                fwidth += indentation
            else:
                try:
                    nwidth = len(str(int(float(results[key]))))
                except Exception:
                    nwidth = 0
                fwidth = len(key.strip())
            if fwidth > width:
                width = fwidth
            if nwidth > integer_width:
                integer_width = nwidth
        return [width, integer_width]

    def __print_subreport(self, results: dict, headers: list, key_column=0, value_column=0,
                          depth_indentation=None, integer_width=0, outfile=sys.stdout):
        """
        Print a sub-report recursively

        :param results: Results to be printed
        :param headers: List of headers to be used for nested components
        :param key_column: Left column for printing of keys (incremented recursively)
        :param value_column: Left column for printing of values
        :param depth_indentation: Per-level indentation
        :param integer_width: (maximum) width for the integer component of any numbers
                               Strings are treated as having zero integer width,
                               but this value is used to determine string indentation
                               so that if possible strings are right aligned with
                               integers
        """
        def indent(string: str, target_column: int):
            return textwrap.indent(string, prefix=' ' * (target_column + 2))[target_column+2:]

        header_keys = []
        value_keys = []
        if depth_indentation is None:
            depth_indentation = self._summary_indent
        for key in results.keys():
            if key in results:
                if isinstance(results[key], dict):
                    header_keys.append(key)
                else:
                    value_keys.append(key)

        header_name = None
        if key_column > 0 and len(headers):
            headers = deepcopy(headers)
            header_name = headers.pop(0)
        for key in header_keys:
            if header_name:
                print(f'{" " * key_column}{header_name}: {key}:', file=outfile)
            else:
                print(f'{" " * key_column}{key.strip()}:', file=outfile)
            self.__print_subreport(results[key], headers, key_column=key_column + depth_indentation, value_column=value_column,
                                   depth_indentation=depth_indentation, integer_width=integer_width, outfile=outfile)
        for key in value_keys:
            value = results[key]
            try:
                nwidth = len(str(int(float(value))))
            except Exception:
                value = str(value).strip()
                if len(value) > integer_width:
                    nwidth = None
                else:
                    nwidth = len(value)
            if nwidth is None:
                integer_indent = 0
            else:
                integer_indent = integer_width - nwidth
            value = str(value)
            if "\n" in value:
                value = textwrap.indent(value, prefix = ' ' * (key_column + 2))
                print(f'{" " * key_column}{key}:\n{value}', file=outfile)
            else:
                print(f'{" " * key_column}{key}: {" " * (value_column + integer_indent - key_column - len(key))}{value}', file=outfile)
        if len(header_keys) == 0:
            print('', file=outfile)

    def __print_report(self, results: dict, value_column=0, integer_width=0, outfile=sys.stdout):
        """
        Print report.  Headers are used by key.

        :param results: Results to be printed
        :param value_column: Left column for printing of values
        :param integer_width: (maximum) width for the integer component of any numbers
                               Strings are treated as having zero integer width,
                               but this value is used to determine string indentation
                               so that if possible strings are right aligned with
                               integers
        """
        for key in results.keys():
            headers = []
            if key in self._header_keys:
                headers = self._header_keys[key]
            if len(results[key].keys()):
                print(f'{key}:', file=outfile)
                self.__print_subreport(results[key], headers=headers, key_column=self._summary_indent, value_column=value_column,
                                       depth_indentation=self._summary_indent, integer_width=integer_width, outfile=outfile)

    def __create_text_report(self, outfile=sys.stdout):
        """
        Create textual report.
        """
        results = {}
        results['Overview'] = {}
        results['Overview']['Job Name'] = self._jdata['metadata']['job_name']
        results['Overview']['Start Time'] = self._jdata['metadata']['cluster_start_time']
        if self._format == 'verbose' and len(self._rows):
            results['Detail'] = {}
            self._rows.sort(key=self.__row_name)
            for row in self._rows:
                if 'Detail' in self._header_keys:
                    header = deepcopy(self._header_keys['Detail'])
                else:
                    header = []
                self._generate_row(results['Detail'], row)
        if len(self._rows) > 0:
            results['Summary'] = {}
            self._generate_summary(results['Summary'])
            results['Overview']['Status'] = 'Success'
        else:
            results['Overview']['Status'] = 'FAILED, no data generated'

        results['Overview']['Workload'] = self._jdata['metadata']['workload']
        results['Overview']['Job UUID'] = self._jdata['metadata']['run_uuid']
        results['Overview']['Run host'] = self._jdata['metadata']['runHost']
        results['Overview']['Kubernetes version'] = self._jdata['metadata']['kubernetes_version']['serverVersion']['gitVersion']
        if 'openshiftVersion' in self._jdata['metadata']['kubernetes_version']:
            results['Overview']['OpenShift Version'] = self._jdata['metadata']['kubernetes_version']['openshiftVersion']
        key_width, integer_width = self.__compute_report_width(results)
        cmdline = ' '.join(self._jdata['metadata']['expanded_command_line'])
        cmdline = self._wrap_text(' '.join(self._jdata['metadata']['expanded_command_line']))
        results['Overview']['Command line'] = cmdline
        self.__print_report(results, value_column=key_width, integer_width=integer_width, outfile=outfile)
