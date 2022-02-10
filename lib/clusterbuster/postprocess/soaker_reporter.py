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
from lib.clusterbuster.postprocess.Reporter import Reporter
from lib.clusterbuster.postprocess.VerboseHeader import VerboseHeader

class soaker_reporter(Reporter):
    def __init__(self, jdata: dict, report_format: str):
        Reporter.__init__(self, jdata, report_format)
        self._summary['total_iterations'] = 0

    def create_row(self, row: dict):
        rowhash = self._rows[Reporter.create_row(self, row)]
        rowhash['iterations'] = row['work_iterations']
        self._summary['total_iterations'] += rowhash['iterations']

    def print_summary(self):
        # I'd like to do this, but if the nodes are out of sync time-wise, this will not
        # function correctly.
        Reporter.print_summary(self)
        print(f"""    Interations:                {self._summary['total_iterations']}
    Interations/sec:            {round(self._summary['total_iterations'] / self._summary['elapsed_time_net'])}
    Interations/CPU sec:        {round(self._summary['total_iterations'] / self._summary['cpu_seconds'])}""")

    def print_verbose(self):
        lastNamespace = None
        lastPod = None
        lastContainer = None
        lastPid = None
        self._rows.sort(key=self.row_name)
        header = VerboseHeader(['namespace', 'pod', 'container', 'process_id'])
        for row in self._rows:
            Reporter.print_verbose(row)
            header.print_header(row)
            print(f"""            Elapsed Time:       {round(row['runtime'], 3)}
            Iterations:         {row['iterations']}
            Iterations/sec:     {round(row['iterations'] / row['runtime'])}
            Iterations/CPU sec: {round(row['iterations'] / (row['user_cpu_seconds'] + row['system_cpu_seconds']))}
""")
