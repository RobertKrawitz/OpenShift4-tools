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


class Reporter:
    def are_clients_all_on_same_node(self):
        node = None
        for obj in self._jdata['api_objects']:
            if obj['kind'] == 'Pod' and 'clusterbuster-client' in obj['labels'] and obj['labels']['clusterbuster-client']:
                if not node:
                    node = obj['nodeName']
                elif obj['nodeName'] != node:
                    return False
        return True

    def find_node_for_pod(self, namespace: str, pod: str):
        for obj in self._jdata['api_objects']:
            if obj['kind'] == 'Pod' and obj['namespace'] == namespace and obj['name'] == pod:
                return obj['nodeName']
        return None

    def __init__(self, jdata: dict, report_format: str):
        self._jdata = deepcopy(jdata)
        self._format = report_format
        self._all_clients_are_on_the_same_node = self.are_clients_all_on_same_node()
        self._summary = {'user_cpu_seconds': 0,
                         'system_cpu_seconds': 0,
                         'cpu_seconds': 0,
                         'first_start': None,
                         'last_start': None,
                         'first_end': None,
                         'last_end': None,
                         'first_pod_start': None,
                         'last_pod_start': None,
                         'first_pod_create': None,
                         'last_pod_create': None,
                         'total_elapsed_time': 0,
                         'total_instances': 0}
        self._rows = []
                      
    def row_name(self, row: dict):
        return f'{row["namespace"]}~{row["pod"]}~{row["container"]}'

    def create_row(self, row: dict):
        rowhash = {}
        rowhash['namespace'] = row['namespace']
        rowhash['pod'] = row['pod']
        rowhash['container'] = row['container']
        rowhash['node'] = self.find_node_for_pod(namespace=row['namespace'], pod=row['pod'])
        rowhash['user_cpu_seconds'] = row['user_cpu_time']
        self._summary['user_cpu_seconds'] += row['user_cpu_time']
        rowhash['system_cpu_seconds'] = row['system_cpu_time']
        self._summary['system_cpu_seconds'] += row['system_cpu_time']
        rowhash['cpu_seconds'] = row['user_cpu_time'] + row['system_cpu_time']
        self._summary['cpu_seconds'] += row['user_cpu_time'] + row['system_cpu_time']
        rowhash['runtime'] = row['data_elapsed_time']
        # Pod create time is relative to the host
        rowhash['pod_create'] = row['pod_create_time_offset_from_base']
        if self._summary['first_pod_create'] is None or rowhash['pod_create'] < self._summary['first_pod_create']:
            self._summary['first_pod_create'] = rowhash['pod_create']
        if self._summary['last_pod_create'] is None or rowhash['pod_create'] > self._summary['last_pod_create']:
            self._summary['last_pod_create'] = rowhash['pod_create']
        self._summary['total_elapsed_time'] += rowhash['runtime']
        self._summary['total_instances'] += 1
        # I'd like to do this, but if the nodes are out of sync time-wise, this will not
        # function correctly.
        if self._all_clients_are_on_the_same_node:
            rowhash['run_start'] = row['data_start_time_offset_from_base']
            rowhash['run_end'] = row['data_end_time_offset_from_base']
            rowhash['pod_start'] = row['pod_start_time_offset_from_base']
            if self._summary['first_start'] is None or rowhash['run_start'] < self._summary['first_start']:
               self._summary['first_start'] = rowhash['run_start']
            if self._summary['first_end'] is None or rowhash['run_end'] < self._summary['first_end']:
               self._summary['first_end'] = rowhash['run_end']
            if self._summary['last_start'] is None or rowhash['run_start'] > self._summary['last_start']:
               self._summary['last_start'] = rowhash['run_start']
            if self._summary['last_end'] is None or rowhash['run_end'] > self._summary['last_end']:
               self._summary['last_end'] = rowhash['run_end']
            if self._summary['first_pod_start'] is None or rowhash['pod_start'] < self._summary['first_pod_start']:
               self._summary['first_pod_start'] = rowhash['pod_start']
            if self._summary['last_pod_start'] is None or rowhash['pod_start'] > self._summary['last_pod_start']:
               self._summary['last_pod_start'] = rowhash['pod_start']
        self._rows.append(rowhash)
        return len(self._rows)-1

    def print_summary(self):
        self._summary['elapsed_time_average'] = self._summary['total_elapsed_time'] / self._summary['total_instances']
        self._summary['pod_create_span'] = self._summary['last_pod_create'] - self._summary['first_pod_create']
        if self._all_clients_are_on_the_same_node:
            self._summary['elapsed_time_net'] = self._summary['last_end'] - self._summary['first_start']
            self._summary['pod_start_span'] = self._summary['last_pod_start'] - self._summary['first_pod_start']
            self._summary['overlap_error'] = ((((self._summary['last_start'] - self._summary['first_start']) +
                                         (self._summary['last_end'] - self._summary['first_end'])) / 2) /
                                        self._summary['elapsed_time_average'])
        print(f"""Summary:
    Total Clients:              {self._summary['total_instances']}
    Elapsed Time Average:       {round(self._summary['elapsed_time_average'], 3)}
    Pod creation span:          {round(self._summary['pod_create_span'], 5)}
    User CPU seconds:           {round(self._summary['user_cpu_seconds'], 3)}
    System CPU seconds:         {round(self._summary['system_cpu_seconds'], 3)}
    CPU seconds:                {round(self._summary['cpu_seconds'], 5)}""")
        if self._all_clients_are_on_the_same_node:
            print(f"""    CPU utilization:            {round(self._summary['cpu_seconds'] / self._summary['elapsed_time_net'], 5)}
    First run start:            {round(self._summary['first_start'], 3)}
    First run end:              {round(self._summary['first_end'], 3)}
    Last run start:             {round(self._summary['last_start'], 3)}
    Last run end:               {round(self._summary['last_end'], 3)}
    Net elapsed time:           {round(self._summary['elapsed_time_net'], 3)}
    Overlap error:              {round(self._summary['overlap_error'], 5)}
    Pod start span:             {round(self._summary['pod_start_span'], 5)}""")
        else:
            print(f'''
    *** Run start/end not available when client pods are not all on the same node ***''')

    def print_verbose(self):
        pass

    def create_report(self):
        if 'Results' in self._jdata:
            rows = self._jdata['Results']
            for row in rows:
                self.create_row(row)

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
                print(f"""Clusterbuster run report for job {self._jdata['metadata']['job_name']} at {self._jdata['metadata']['job_start_time']}

    Workload: {self._jdata['metadata']['workload']}
    Command line:  {textwrap.fill(' '.join(self._jdata['metadata']['expanded_command_line']), width=72, subsequent_indent='                ', break_long_words=False, break_on_hyphens=False)}
""")
                if self._format == 'verbose':
                    self.print_verbose()
                self.print_summary()
