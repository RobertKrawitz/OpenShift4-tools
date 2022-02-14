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
from lib.clusterbuster.postprocess.ClusterBusterReporter import ClusterBusterReporter

class files_reporter(ClusterBusterReporter):
    def __init__(self, jdata: dict, report_format: str):
        ClusterBusterReporter.__init__(self, jdata, report_format)
        self.initialize_timeline_vars(['create.operation_start', 'remove.operation_start'])
        self.initialize_accumulators(['create.operation_elapsed_time', 'create.user_cpu_time', 'create.system_cpu_time', 'create.cpu_time', 'create.operations',
                                      'remove.operation_elapsed_time', 'remove.user_cpu_time', 'remove.system_cpu_time', 'remove.cpu_time', 'remove.operations'])
        self.set_header_components(['namespace', 'pod', 'container', 'process_id'])

    def generate_summary(self, results: dict):
        # I'd like to do this, but if the nodes are out of sync time-wise, this will not
        # function correctly.
        ClusterBusterReporter.generate_summary(self, results)
        for op in ['create', 'remove']:
            cop = op.capitalize()
            results[cop] = {}
            results[cop]['Elapsed Time'] = round(self._summary[op]['operation_elapsed_time'], 3)
            results[cop]['CPU Time'] = round(self._summary[op]['cpu_time'], 3)
            results[cop]['Operations'] = self._summary[op]['operations']
            results[cop]['Operations/sec'] = round(self._summary[op]['operations'] / self._summary[op]['operation_elapsed_time'])
            results[cop]['Operations/CPU sec'] = round(self._summary[op]['operations'] / (self._summary[op]['cpu_time']))

    def generate_row(self, results: dict, row: dict):
        ClusterBusterReporter.generate_row(self, row, results)
        result = {}
        for op in ['create', 'remove']:
            cop = op.capitalize()
            result[cop] = {}
            result[cop]['Elapsed Time'] = round(row[op]['operation_elapsed_time'], 3)
            result[cop]['CPU Time'] = round(row[op]['cpu_time'], 3)
            result[cop]['Operations'] = row[op]['operations']
            result[cop]['Operations/sec'] = round(row[op]['operations'] / row[op]['operation_elapsed_time'])
            result[cop]['Operations/CPU sec'] = round(row[op]['operations'] / (row[op]['cpu_time']))
        results[row['namespace']][row['pod']][row['container']][row['process_id']] = result
