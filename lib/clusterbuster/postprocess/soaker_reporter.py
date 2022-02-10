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

class soaker_reporter(Reporter):
    def __init__(self, jdata: dict, report_format: str):
        Reporter.__init__(self, jdata, report_format)
        self.initialize_accumulators(['work_iterations'])
        self.set_header_components(['namespace', 'pod', 'container', 'process_id'])

    def print_summary(self):
        # I'd like to do this, but if the nodes are out of sync time-wise, this will not
        # function correctly.
        Reporter.print_summary(self)
        self.print_summary_key_value('Interations', self._summary['work_iterations'])
        self.print_summary_key_value('Interations/sec', round(self._summary['work_iterations'] / self._summary['data_run_span']))
        self.print_summary_key_value('Interations/CPU sec', round(self._summary['work_iterations'] / self._summary['cpu_time']))

    def print_verbose(self, row):
        Reporter.print_verbose(self, row)
        self.print_verbose_key_value('Elapsed Time', round(row['data_elapsed_time'], 3))
        self.print_verbose_key_value('iterations', row['work_iterations'])
        self.print_verbose_key_value('iterations/sec', round(row['work_iterations'] / row['data_elapsed_time']))
        self.print_verbose_key_value('iterations/CPU sec', round(row['work_iterations'] / row['cpu_time']))
