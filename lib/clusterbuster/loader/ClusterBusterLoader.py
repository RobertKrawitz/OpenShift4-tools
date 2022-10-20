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
import json
import sys
from lib.clusterbuster.reporter.ClusterBusterReporter import ClusterBusterReporter


class LoadOneReport:
    def __init__(self, report: dict, answer: dict):
        try:
            self._report = report
            self._answer = answer
            self._metadata = self._report['metadata']
            self._summary = self._report['summary']
            self._metrics = self._summary['metrics']
        except Exception:
            if getattr(self, '_report', None) is None:
                self._report = {}
            if getattr(self, '_answer', None) is None:
                self._answer = {}
            if 'metadata' not in self._report:
                self._metadata = {}
            if 'summary' not in self._report:
                self._summary = {
                    'results': {},
                    'metrics': {}
                    }
            if 'metrics' not in self._summary:
                self._metrics = {}
        if 'metadata' not in answer or 'uuid' not in answer['metadata']:
            answer['metadata'] = dict()
            answer['metadata']['start_time'] = self._metadata['cluster_start_time']
            answer['metadata']['uuid'] = self._metadata['uuid']
            answer['metadata']['server_version'] = self._metadata['kubernetes_version']['serverVersion']
            answer['metadata']['openshift_version'] = self._metadata['kubernetes_version']['openshiftVersion']
            answer['metadata']['run_host'] = self._metadata['runHost']
            answer['metadata']['kata_version'] = self._metadata.get('kata_version')
        else:
            if self._metadata['cluster_start_time'] < answer['metadata']['start_time']:
                answer['metadata']['start_time'] = self._metadata['cluster_start_time']
                if self._metadata['uuid'] != answer['metadata']['uuid']:
                    raise Exception(f"Mismatched uuid: {self._metadata['uuid']}, {answer['metadata']['uuid']}")
                if self._metadata['runHost'] != answer['metadata']['run_host']:
                    raise Exception(f"Mismatched run_host: {self._metadata['runHost']}, {answer['metadata']['run_host']}")
                if self._metadata['kubernetes_version']['openshiftVersion'] != answer['metadata']['openshift_version']:
                    raise Exception(f"Mismatched openshift_version: {self._metadata['kubernetes_version']['openshiftVersion']}, {answer['metadata']['openshift_version']}")
                if self._metadata['kubernetes_version']['serverVersion'] != answer['metadata']['server_version']:
                    raise Exception(f"Mismatched server_version: {self._metadata['kubernetes_version']['serverVersion']}, {answer['metadata']['server_version']}")
                if self._metadata.get('kata_version') != answer['metadata']['kata_version']:
                    raise Exception(f"Mismatched kata_version: {self._metadata.get('kata_version')}, {answer['metadata']['kata_version']}")
        if self._metadata['kind'] != 'clusterbusterResults':
            raise Exception("Invalid results file")
        if 'runtime_class' in self._metadata and self._metadata['runtime_class'] == 'kata':
            self._runtime_env = 'kata'
        else:
            self._runtime_env = 'runc'
        try:
            self._client_pin_node = self._metadata['options']['pin_nodes']['client']
        except Exception:
            self._client_pin_node = None
        self._count = self._summary['total_instances']
        self._workload = self._metadata['workload']

    def _MakeHierarchy(self, hierarchy: dict, keys: list):
        key = keys.pop(0)
        if key not in hierarchy:
            hierarchy[key] = dict()
        if keys:
            self._MakeHierarchy(hierarchy[key], keys)

    def Load(self):
        pass


class ClusterBusterLoader:
    """
    Analyze ClusterBuster reports
    """

    def __init__(self, dirs_and_files: list):
        self.reports = ClusterBusterReporter.report(dirs_and_files, format="json-summary")
        dirs = []
        self.status = {}
        for d in dirs_and_files:
            if d in dirs:
                continue
            if os.path.isdir(d):
                dirs.append(d)
                if  os.path.isfile(os.path.join(d, "clusterbuster-ci-results.json")):
                    with open(os.path.join(d, "clusterbuster-ci-results.json")) as f:
                        dir_status = json.load(f)
                        if 'result' not in self.status or dir_status.get('result', 'FAIL') != 'PASS':
                            self.status['result'] = dir_status['result']
                        if 'job_start' not in self.status or dir_status['job_start'] < self.status['job_start']:
                            self.status['job_start'] = dir_status['job_start']
                        if 'job_end' not in self.status or dir_status['job_end'] > self.status['job_end']:
                            self.status['job_end'] = dir_status['job_end']
                        self.status['job_runtime'] = self.status.get('job_runtime', 0) + dir_status['job_runtime']
                        if 'ran' not in self.status:
                            self.status['ran'] = dir_status['ran']
                        else:
                            self.status['ran'].extend(dir_status['ran'])
                        if 'failed' not in self.status:
                            self.status['failed'] = dir_status['failed']
                        else:
                            self.status['failed'].extend(dir_status['failed'])
                else:
                    print(f'Summary {os.path.join(d, "clusterbuster-ci-results.json")} expected but not present', file=sys.stderr)
            else:
                print(f'{d}: not a directory')
        if not self.status:
            print(f'Unable to load {dirs_and_files}', file=sys.stderr)

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
                    i[1](report, answer).Load()
        answer['status'] = self.status
        return answer
