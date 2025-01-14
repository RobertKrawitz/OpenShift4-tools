#!/usr/bin/env python3

# Copyright 2023 Robert Krawitz/Red Hat
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

import argparse
import json
from copy import deepcopy
import traceback
import sys
from .ClusterBusterReporter import ClusterBusterReporter


class memory_reporter(ClusterBusterReporter):

    TIMELINE_FORMATS = ['tsv', 'csv', 'json']
    SEPARATORS = {
        'tsv': '\t',
        'csv': ','
        }
    COLUMNS = {
        'time': {
            'header': 'Time',
            'precise_format': '%.3f',
            'format': '%.0f'
            },
        'current_request': {
            'header': 'Workload Memory Request'
            },
        'current_in_use': {
            'header': 'Workload Memory In Use'
            },
        'jobs': {
            'header': 'Jobs',
            'format': False
            },
        'max': {
            'header': 'Maximum Workload Request'
            },
        'work_rate': {
            'header': 'Work Rate',
            'round': 0
            },
        'node_in_use': {
            'header': 'Node Memory In Use'
            },
        'working_set': {
            'header': 'Cgroup Memory In Use'
            },
        'node_CPU': {
            'header': 'Node CPU',
            'format': False
            },
        'container_CPU': {
            'header': 'Cgroup CPU',
            'format': False
            },
        }

    def __init__(self, jdata: dict, report_format: str, extras=None):
        super().__init__(jdata, report_format, extras=extras)
        parser = argparse.ArgumentParser(description='Parse memory report')
        parser.add_argument('--dense-timeline', '--dense', type=float, nargs='?', const=1.0, help='Print dense timeline')
        parser.add_argument('--precise-timeline', '--precise', action='store_true', help='Print high precision timeline')
        parser.add_argument('--numeric-timeline', action='store_true', help='Print scannable numbers')
        parser.add_argument('--timeline-format', type=str, choices=self.TIMELINE_FORMATS,
                            help=f'Timeline format: one of {", ".join(self.TIMELINE_FORMATS)}',
                            default='tsv')
        parser.add_argument('--timeline-file', type=str, help='Output file for timeline')
        parser.add_argument('--timeline-column', action='append', help='Column options (see the code)')
        self.args, self.extra_args = parser.parse_known_args(extras)
        if self.args.dense_timeline is not None:
            if float(self.args.dense_timeline) <= 0:
                raise ValueError('--dense-timeline must be greater than 0')
        self.work = {}
        self.work_total = 0
        self.pod_node = {}
        self.start_times = {}
        self.end_times = {}
        self.net_start_time = None
        self.net_end_time = None
        self.timeline = None
        self.scan = "None"
        try:
            scantype = jdata['metadata']['options']['workload_options']['memory_scan']
            if scantype == 1:
                self.scan = 'Sequential'
            elif scantype == 2:
                self.scan = 'Random'
        except KeyError:
            pass
        self._add_explicit_timeline_vars(['cases.alloc_time', 'cases.prefree_time', 'cases.runtime', 'cases.run_start_time'])
        self._add_accumulators(['total_pages', 'cases.runtime', 'cases.prefree_time', 'cases.run_start_time'])
        for obj in jdata.get('api_objects', []):
            try:
                name = f'{obj["metadata"]["name"]}.{obj["metadata"]["namespace"]}'
                if obj.get('kind', None) == 'Pod':
                    self.pod_node[name] = obj['spec']['nodeName']
                elif obj.get('kind', None) == 'VirtualMachineInstance':
                    self.pod_node[name] = list(obj['status']['activePods'].values())[0]
            except KeyError:
                pass
        self._set_header_components(['namespace', 'pod', 'container', 'process_id'])
        self._add_fields_to_copy(["result.scan"])
        self.columns = deepcopy(self.COLUMNS)
        if self.args.timeline_column:
            for arg in self.args.timeline_column:
                try:
                    name, data = arg.split(':', 2)
                except ValueError:
                    continue
                if name == '' or name == '-':
                    continue
                if name.startswith('-'):
                    self.columns.pop(name, None)
                if name not in self.columns:
                    self.columns[name] = {}
                for param in data.split(';'):
                    try:
                        key, value = param.split('=')
                    except ValueError:
                        pass
                    if key.startswith('!'):
                        value = False
                    elif key.startswith('+'):
                        value = True
                    elif key.startswith('-'):
                        self.columns[name].pop(key, None)
                    else:
                        self.columns[name][key] = value

    def timeint(self, val: float):
        if self.args.dense_timeline:
            return val / self.args.dense_timeline
        else:
            return val

    def inttime(self, val: float):
        if self.args.dense_timeline:
            if self.args.dense_timeline % 1:
                return val * self.args.dense_timeline
            else:
                return int((val + .000000001) * self.args.dense_timeline)
        else:
            return val

    def __build_timeline(self):
        timeline = {}
        events = None
        if 'Results' in self._jdata and 'worker_results' in self._jdata['Results']:
            events = {}
            for result in self._jdata['Results']['worker_results']:
                if "pod" not in result or "namespace" not in result:
                    continue
                name = f'{result["pod"]}.{result["namespace"]}'
                node = self.pod_node[name]
                if node not in timeline:
                    events[node] = []
                    self.work[node] = 0
                    self.start_times[node] = None
                    self.end_times[node] = None
                    timeline[node] = {}
                    timeline[node][0.0] = {'request': 0, 'in_use': 0, 'jobs': 0, 'rate': 0, 'events': {}}
                for case in result['cases']:
                    start_time = case['start_time'] - self._summary['first_pod_start_time']
                    end_time = case['end_time'] - self._summary['first_pod_start_time']
                    if 'prealloc_time' in case:
                        alloc_time = case['alloc_time'] - self._summary['first_pod_start_time']
                        prefree_time = case['prefree_time'] - self._summary['first_pod_start_time']
                    else:
                        alloc_time = start_time
                        prefree_time = end_time
                    if self.net_start_time is None or start_time < self.net_start_time:
                        self.net_start_time = start_time
                    if self.net_end_time is None or end_time > self.net_end_time:
                        self.net_end_time = end_time
                    if self.start_times[node] is None or start_time < self.start_times[node]:
                        self.start_times[node] = start_time
                    if self.end_times[node] is None or end_time > self.end_times[node]:
                        self.end_times[node] = end_time
                    elapsed = prefree_time - alloc_time
                    pages = case['pages']
                    memory = case['size']
                    self.work[node] += pages
                    self.work_total += pages
                    for time in [start_time, alloc_time, prefree_time, end_time]:
                        if time not in timeline[node]:
                            timeline[node][time] = {'request': 0, 'in_use': 0, 'jobs': 0, 'rate': 0, 'events': {}}
                    timeline[node][start_time]['events']['alloc'] = 1
                    timeline[node][start_time]['request'] += memory
                    timeline[node][alloc_time]['events']['inuse'] = 1
                    timeline[node][alloc_time]['jobs'] += 1
                    timeline[node][alloc_time]['in_use'] += memory
                    timeline[node][alloc_time]['rate'] += pages / elapsed
                    timeline[node][prefree_time]['events']['free'] = 1
                    timeline[node][prefree_time]['request'] -= memory
                    timeline[node][prefree_time]['jobs'] -= 1
                    timeline[node][prefree_time]['rate'] -= pages / elapsed
                    timeline[node][end_time]['events']['done'] = 1
                    timeline[node][end_time]['in_use'] -= memory
            current_request = 0
            current_in_use = 0
            max = 0
            jobs = 0
            rate = 0
            for node, subtimeline in timeline.items():
                current_idx = -1
                inode = {'instance': node}
                nnode = {'node': node}
                for time in sorted(subtimeline.keys()):
                    e = subtimeline[time]
                    request = e['request']
                    in_use = e['in_use']
                    jobs += e['jobs']
                    rate += e['rate']
                    current_request += request
                    current_in_use += in_use
                    if current_in_use > max:
                        max = current_in_use
                    if not self.args.precise_timeline:
                        time = self.inttime(int(self.timeint(time)))
                    if ((current_idx >= 0 and self.args.dense_timeline and
                         int(time) > int(self.timeint(events[node][current_idx]['time'])) + 1)):
                        prev = events[node][current_idx]
                        for i in range(int(self.timeint(prev['time'])) + 1, int(self.timeint(time))):
                            itime = self.inttime(i)
                            event = {
                                'time': itime,
                                'jobs': prev['jobs'],
                                'current_request': prev['current_request'],
                                'current_in_use': prev['current_in_use'],
                                'max': prev['max'],
                                'work_rate': prev['work_rate'],
                                'node_in_use': int(self.get_adj_metric('nodeMemoryInUse-Workers', itime, inode)),
                                'working_set': int(self.get_adj_metric('containerMemoryWorkingSet-clusterbuster', itime, nnode)),
                                'node_CPU': round(self.get_adj_metric('nodeCPUUtil-Workers', itime, inode), 3),
                                'container_CPU': round(self.get_adj_metric('containerCPU-clusterbuster', itime, nnode), 3)
                                }
                            events[node].append(event)
                            current_idx += 1
                    event = {
                        'time': time,
                        'request': request,
                        'jobs': jobs,
                        'current_request': current_request,
                        'current_in_use': current_in_use,
                        'max': max,
                        'work_rate': rate,
                        'node_in_use': int(self.get_adj_metric('nodeMemoryInUse-Workers', time, inode)),
                        'working_set': int(self.get_adj_metric('containerMemoryWorkingSet-clusterbuster', time, nnode)),
                        'node_CPU': round(self.get_adj_metric('nodeCPUUtil-Workers', time, inode), 3),
                        'container_CPU': round(self.get_adj_metric('containerCPU-clusterbuster', time, nnode), 3)
                        }
                    if current_idx >= 0 and time == events[node][current_idx]['time']:
                        events[node][current_idx] = event
                    else:
                        events[node].append(event)
                        current_idx += 1
        return events

    def build_timeline(self):
        if self.timeline is None:
            try:
                self.timeline = self.__build_timeline()
            except (TypeError, ValueError, KeyError):
                print(f"Unable to build timeline: {traceback.format_exc()}", file=sys.stderr)
                self.timeline = False
        elif self.timeline is False:
            pass

    def pp(self, val, suffix: str = 'B'):
        if self.args.numeric_timeline:
            return str(int(val))
        else:
            return self._prettyprint(val, precision=3, base=1024, suffix=suffix)

    def format_to_spec(self, value, fmt: str):
        if fmt is False:
            return str(value)
        else:
            return fmt % (value)

    def format_column(self, event: dict, column: str, definition: dict):
        value = event.get(column, 0)
        if 'round' in definition:
            value = round(value, definition['round'])
        if ('precise_format' in definition and
            ((self.args.precise_timeline and 'precise_format' in definition) or
             (self.args.dense_timeline is not None and self.args.dense_timeline % 1))):
            return self.format_to_spec(value, definition['precise_format'])
        elif 'format' in definition:
            return self.format_to_spec(value, definition['format'])
        return self.pp(value)

    def format_timeline_text(self, timeline_format=None):
        if timeline_format is None:
            timeline_format = 'tsv'
        sep = self.SEPARATORS[timeline_format]
        return '\n'.join([f"Node: {node}\n{sep.join([col['header'] for col in self.columns.values()])}\n" +
                          '\n'.join([sep.join([self.format_column(event, name, column)
                                               for name, column in self.columns.items()])
                                     for event in self.timeline[node]])
                          for node in sorted(self.timeline.keys())])

    def format_timeline(self, report_format=None, timeline_format=None):
        if report_format is None:
            report_format = self._report_format
        if timeline_format is not None:
            if self.timeline is None:
                return None if timeline_format == 'json' else ''
            if timeline_format == 'json':
                return json.dumps(self.timeline, indent=2)
            else:
                return self.format_timeline_text(timeline_format)
        elif self.timeline is None or report_format is None or 'summary' in report_format:
            return None
        elif report_format == 'verbose':
            return self.format_timeline_text()
        else:
            return self.timeline

    def get_adj_metric(self, metric_name: str, time: float, selector: dict = None):
        answer = self._get_metric_value(metric_name, time + self._summary['first_pod_start_time'], selector)
        if answer is None:
            return 0
        else:
            return answer

    def _generate_summary(self, results: dict):
        # I'd like to do this, but if the nodes are out of sync time-wise, this will not
        # function correctly.
        ClusterBusterReporter._generate_summary(self, results)
        self.build_timeline()
        results['Pages Scanned'] = self._prettyprint(self._summary['total_pages'],
                                                     precision=3, base=1000, suffix=' pp')
        self._summary['job_runtime'] = self._summary['last_prefree_time'] - self._summary['last_alloc_time']
        if self.net_end_time is not None and self.net_start_time is not None:
            results['Pages Scanned/sec'] = self._prettyprint(self._safe_div(self._summary['total_pages'],
                                                                            self._summary['job_runtime']),
                                                             precision=3, base=1000, suffix=' pp/sec')
            self._summary['pages_scanned_sec'] = self._safe_div(self._summary['total_pages'],
                                                                self._summary['job_runtime'])
        results['Scan Pattern'] = self.scan
        self._summary['scan_pattern'] = self.scan
        if self.args.timeline_file:
            if self.timeline:
                timeline_report = self.format_timeline(timeline_format=self.args.timeline_format)
                if self.args.timeline_file == '-':
                    print(timeline_report)
                with open(self.args.timeline_file, 'w') as fp:
                    print(timeline_report, file=fp)
            else:
                raise TypeError("Unable to report timeline: no events")
        timeline = self.format_timeline()
        if timeline:
            results['Timeline'] = timeline

    def _generate_row(self, results: dict, row: dict):
        ClusterBusterReporter._generate_row(self, results, row)
        runtime = row['prefree_time'] - row['run_start_time'] if 'run_start_time' in row else row['runtime']
        result = {}
        result['Pages Scanned/sec'] = self._prettyprint(self._safe_div(row['total_pages'], runtime),
                                                        precision=3, base=1000, suffix=' pp/sec')
        row['pages_scanned_sec'] = self._safe_div(row['total_pages'], runtime)
        result['Pages Scanned'] = self._prettyprint(row['total_pages'], precision=3, base=1000, suffix=' pp/sec')
        self._insert_into(results, [row['namespace'], row['pod'], row['container'], str(row['process_id'])], result)
