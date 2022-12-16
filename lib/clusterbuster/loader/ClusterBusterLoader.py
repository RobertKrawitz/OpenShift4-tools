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

import importlib
import inspect
import os
import sys
from datetime import datetime
from lib.clusterbuster.reporter.ClusterBusterReporter import ClusterBusterReporter


class ClusterBusterLoader:
    """
    Analyze ClusterBuster reports
    """

    def __init__(self, dirs: list):
        self.reports = ClusterBusterReporter.report(dirs, format="json-summary")
        self.status = {
            'result': None,
            'ran': [],
            'failed': [],
            'job_start': None,
            'job_end': None,
            'job_runtime': None
            }
        for directory in dirs:
            if os.path.isdir(directory):
                run_start = None
                run_end = None
                for report in self.reports:
                    if 'metadata' in report:
                        metadata = report['metadata']
                        if 'controller_second_start_timestamp' in metadata:
                            job_start = metadata['controller_second_start_timestamp']
                            job_end = metadata['controller_end_timestamp']
                            if run_start is None or job_start < run_start:
                                run_start = job_start
                                self.status['job_start'] = datetime.strftime(datetime.fromtimestamp(job_start), '%Y-%m-%dT%T+00:00')
                            if run_end is None or job_end > run_end:
                                run_end = job_end
                                self.status['job_end'] = datetime.strftime(datetime.fromtimestamp(job_end), '%Y-%m-%dT%T+00:00')
                            self.status['job_runtime'] = round(run_end - run_start)
                            if report['Status'] == 'Pass' or report['Status'] == 'Success':
                                self.status['ran'].append(metadata['job_name'])
                            elif report['Status'] == 'Fail':
                                self.status['failed'].append(metadata['job_name'])
                            elif report['Status'] != 'No Result':
                                raise ValueError(f'Status should be Pass, Fail, or No Result; actual was {report["Status"]}')
            else:
                print(f'{directory}: not a directory')
            if not self.status['job_runtime']:
                print(f'Unable to load {directory}', file=sys.stderr)

    def Load(self):
        answer = dict()
        for report in self.reports:
            workload = report['metadata']['workload']
            try:
                imported_lib = importlib.import_module(f'..{workload}_loader', __name__)
            except Exception:
                continue
            for i in inspect.getmembers(imported_lib):
                if i[0] == f'{workload}_loader':
                    try:
                        i[1](report, answer).Load()
                    except Exception:
                        print(f'Loading report {report["metadata"]["RunArtifactDir"]} failed: {sys.exc_info()}', file=sys.stderr)
        answer['status'] = self.status
        return answer
