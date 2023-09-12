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

from .ClusterBusterReporter import ClusterBusterReporter


class memory_reporter(ClusterBusterReporter):
    def __init__(self, jdata: dict, report_format: str):
        super().__init__(jdata, report_format)
        self.work = {}
        self.work_total = 0
        pod_node = {}
        self.start_times = {}
        self.end_times = {}
        self.net_start_time = None
        self.net_end_time = None
        for obj in jdata.get('api_objects', []):
            try:
                name = f'{obj["metadata"]["name"]}.{obj["metadata"]["namespace"]}'
                if obj.get('kind', None) == 'Pod':
                    node = obj['spec']['nodeName']
                elif obj.get('kind', None) == 'VirtualMachineInstance':
                    node = list(obj['status']['activePods'].values())[0]
                pod_node[name] = node
            except KeyError:
                pass
        timeline = {}
        self.events = None
        if 'Results' in jdata and 'worker_results' in jdata['Results']:
            self.events = {}
            for result in jdata['Results']['worker_results']:
                name = f'{result["pod"]}.{result["namespace"]}'
                node = pod_node[name]
                if node not in timeline:
                    self.events[node] = []
                    self.work[node] = 0
                    self.start_times[node] = None
                    self.end_times[node] = None
                    timeline[node] = {}
                    timeline[node][0.0] = {'increment': 0, 'active': 0, 'rate': 0}
                for case in result['cases']:
                    start_time = case['start_time']
                    end_time = case['end_time']
                    if self.net_start_time is None or start_time < self.net_start_time:
                        self.net_start_time = start_time
                    if self.net_end_time is None or end_time > self.net_end_time:
                        self.net_end_time = end_time
                    if self.start_times[node] is None or start_time < self.start_times[node]:
                        self.start_times[node] = start_time
                    if self.end_times[node] is None or end_time > self.end_times[node]:
                        self.end_times[node] = end_time
                    elapsed = end_time - start_time
                    pages = case['pages']
                    memory = case['size']
                    self.work[node] += pages
                    self.work_total += pages
                    if start_time in timeline[node]:
                        timeline[node][start_time]['increment'] += memory
                        timeline[node][start_time]['active'] += 1
                        timeline[node][start_time]['rate'] += pages / elapsed
                    else:
                        timeline[node][start_time] = {'increment': memory}
                        timeline[node][start_time]['active'] = 1
                        timeline[node][start_time]['rate'] = pages / elapsed
                    if end_time in timeline[node]:
                        timeline[node][end_time]['increment'] -= memory
                        timeline[node][end_time]['active'] -= 1
                        timeline[node][end_time]['rate'] -= pages / elapsed
                    else:
                        timeline[node][end_time] = {'increment': -memory}
                        timeline[node][end_time]['active'] = -1
                        timeline[node][end_time]['rate'] = -pages / elapsed
            current = 0
            max = 0
            active = 0
            rate = 0
            for node, subtimeline in timeline.items():
                for time in sorted(subtimeline.keys()):
                    e = subtimeline[time]
                    increment = e['increment']
                    active += e['active']
                    current += increment
                    rate += e['rate']
                    if current > max:
                        max = current
                    event = {
                        'time': time,
                        'increment': increment,
                        'active': active,
                        'current': current,
                        'max': max,
                        'work_rate': rate
                        }
                    self.events[node].append(event)
        self._set_header_components(['namespace', 'pod', 'container', 'process_id'])

    def pp(self, val, suffix: str = 'B'):
        return self._prettyprint(val, precision=3, base=1024, suffix=suffix)

    def format_timeline(self, timeline: dict):
        if self.events is None or self._report_format == 'none' or 'summary' in self._report_format:
            return None
        elif self._report_format == 'verbose':
            return '\n'.join([f'Node: {node}\n  ' +
                              '\n  '.join(['Time %10.3f  In Use %12s  Delta %13s  Jobs %4d  Maximum %12s  Rate %18s' %
                                           (event['time'], self.pp(event['current']), self.pp(event['increment']),
                                            event['active'], self.pp(event['max']),
                                            self.pp(round(event['work_rate'], 0), ' pp/sec'))
                                           for event in timeline[node]])
                              for node in sorted(timeline.keys())])
        else:
            return timeline

    def _generate_summary(self, results: dict):
        # I'd like to do this, but if the nodes are out of sync time-wise, this will not
        # function correctly.
        ClusterBusterReporter._generate_summary(self, results)
        results['Pages Scanned'] = self._prettyprint(self.work_total,
                                                  precision=3, base=1000, suffix=' it')
        results['Pages Scanned/sec'] = self._prettyprint(self._safe_div(self.work_total,
                                                                        self.net_end_time - self.net_start_time),
                                                      precision=3, base=1000, suffix=' pp/sec')
        timeline = self.format_timeline(self.events)
        if timeline:
            results['Timeline'] = timeline

    def _generate_row(self, results: dict, row: dict):
        ClusterBusterReporter._generate_row(self, results, row)
