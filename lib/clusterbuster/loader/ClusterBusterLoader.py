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
import re
from datetime import datetime
from lib.clusterbuster.reporter.ClusterBusterReporter import ClusterBusterReporter


class LoadOneReport:
    def __init__(self, name: str, report: dict, data: dict):
        self._name = name
        self._data = data
        self._report = report
        try:
            self._metadata = self._report['metadata']
            self._summary = self._report['summary']
            self._metrics = self._summary['metrics']
            if 'Status' in self._report:
                self._status = self._report['Status']
            else:
                self._status = 'Success'
        except Exception:
            if getattr(self, '_status', None) is None:
                self._status = 'Fail'
            if getattr(self, '_report', None) is None:
                self._report = {}
            if 'metadata' not in self._report:
                self._metadata = {}
            if 'summary' not in self._report:
                self._summary = {
                    'results': {},
                    'metrics': {}
                    }
            if 'metrics' not in self._summary:
                self._metrics = {}
        if 'baseline' not in data['metadata']:
            data['metadata']['baseline'] = name
        if name not in data['metadata']['jobs'] or 'uuid' not in data['metadata']['jobs'][name]:
            data['metadata']['jobs'][name] = dict()
            data['metadata']['jobs'][name]['start_time'] = self._metadata['cluster_start_time']
            data['metadata']['jobs'][name]['uuid'] = self._metadata['uuid']
            data['metadata']['jobs'][name]['server_version'] = self._metadata['kubernetes_version']['serverVersion']
            data['metadata']['jobs'][name]['openshift_version'] = self._metadata['kubernetes_version'].get('openshiftVersion', 'Unknown')
            data['metadata']['jobs'][name]['run_host'] = self._metadata['runHost']
            data['metadata']['jobs'][name]['kata_version'] = self._metadata.get('kata_version', None)
            data['metadata']['jobs'][name]['cnv_version'] = self._metadata.get('cnv_version', None)
        else:
            if self._metadata['cluster_start_time'] < data['metadata']['jobs'][name]['start_time']:
                data['metadata']['jobs'][name]['start_time'] = self._metadata['cluster_start_time']
                if self._metadata['uuid'] != data['metadata']['jobs'][name]['uuid']:
                    raise Exception(f"Mismatched uuid: {self._metadata['uuid']}, {data['metadata']['jobs'][name]['uuid']}")
                if self._metadata['runHost'] != data['metadata']['jobs'][name]['run_host']:
                    raise Exception(f"Mismatched run_host: {self._metadata['runHost']}, {data['metadata']['jobs'][name]['run_host']}")
                if self._metadata['kubernetes_version']['openshiftVersion'] != data['metadata']['jobs'][name]['openshift_version']:
                    raise Exception(f"Mismatched openshift_version: {self._metadata['kubernetes_version']['openshiftVersion']}, {data['metadata']['jobs'][name]['openshift_version']}")
                if self._metadata['kubernetes_version']['serverVersion'] != data['metadata']['jobs'][name]['server_version']:
                    raise Exception(f"Mismatched server_version: {self._metadata['kubernetes_version']['serverVersion']}, {data['metadata']['jobs'][name]['server_version']}")
                if self._metadata.get('kata_version') != data['metadata']['jobs'][name]['kata_version']:
                    raise Exception(f"Mismatched kata_version: {self._metadata.get('kata_version')}, {data['metadata']['jobs'][name]['kata_version']}")
        if self._metadata['kind'] != 'clusterbusterResults':
            raise Exception("Invalid results file")
        if 'runtime_class' in self._metadata:
            self._runtime_env = self._metadata['runtime_class']
        else:
            self._runtime_env = 'runc'
        data['metadata']['jobs'][name]['runtime_class'] = self._runtime_env
        if self._metadata['kind'] != 'clusterbusterResults':
            raise Exception("Invalid results file")
        try:
            self._client_pin_node = self._metadata['options']['pin_nodes']['client']
        except Exception:
            self._client_pin_node = None
        self._count = self._summary['total_instances']
        self._workload = self._metadata['workload']

    def _MakeHierarchy(self, hierarchy: dict, keys: list, value: dict = None):
        key = keys.pop(0)
        if key not in hierarchy:
            hierarchy[key] = dict()
        if keys:
            self._MakeHierarchy(hierarchy[key], keys, value)
        elif value:
            hierarchy[key] = value

    def Load(self):
        pass


class LoadReportSet:
    """
    Analyze ClusterBuster reports
    """

    def __init__(self, dirs: list, name: str, answer: dict):
        self.reports = {}
        if dirs:
            self.reports = ClusterBusterReporter.report(dirs, "json-summary")
        status = {
            'result': None,
            'ran': [],
            'failed': [],
            'job_start': None,
            'job_end': None,
            'job_runtime': None
            }
        self.answer = answer
        self.name = name
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
                        status['job_start'] = datetime.strftime(datetime.fromtimestamp(job_start), '%Y-%m-%dT%T+00:00')
                    if run_end is None or job_end > run_end:
                        run_end = job_end
                        status['job_end'] = datetime.strftime(datetime.fromtimestamp(job_end), '%Y-%m-%dT%T+00:00')
                    status['job_runtime'] = round(run_end - run_start)
                    if report['Status'] == 'Pass' or report['Status'] == 'Success':
                        status['ran'].append(f"{name}-{metadata['job_name']}")
                    elif report['Status'] == 'Fail':
                        status['failed'].append(metadata['job_name'])
                    elif report['Status'] != 'No Result':
                        raise ValueError(f'Status should be Pass, Fail, or No Result; actual was {report["Status"]}')
        status['result'] = 'PASS' if not status['failed'] else 'FAIL'
        self.answer['status']['jobs'][self.name] = status

    def Load(self):
        for report in self.reports:
            workload = report['metadata']['workload']
            try:
                imported_lib = importlib.import_module(f'..{workload}_loader', __name__)
            except Exception:
                continue
            for i in inspect.getmembers(imported_lib):
                if i[0] == f'{workload}_loader':
                    try:
                        i[1](self.name, report, self.answer).Load()
                    except Exception:
                        print(f'Loading report {report["metadata"]["RunArtifactDir"]} failed: {sys.exc_info()}', file=sys.stderr)


class ClusterBusterLoader:
    def __init__(self):
        pass

    def _matches_patterns(self, f: str, patterns: list):
        if patterns:
            for pattern in patterns:
                if not re.search(pattern, f):
                    return False
        return True

    def _create_report_spec(self, arg: str):
        answer = {}
        dirname = None
        job_patterns = []
        run_name = None
        name_suffixes = []
        for component in arg.split(':'):
            pair = component.split('=', 1)
            if len(pair) == 1:
                dirname = pair[0]
            else:
                key, value = pair
                key = key.lower()
                if key.startswith('dir'):
                    dirname = value
                elif key == 'job_pattern':
                    job_patterns.append(value)
                elif key == 'name':
                    run_name = value
                elif key == 'name_suffix':
                    name_suffixes.append(value)
                else:
                    raise ValueError(f"Unexpected key {key} in name {arg}")
        if dirname is None:
            raise ValueError(f"No directory name found in {arg}")
        if run_name is None and not name_suffixes:
            run_name = dirname.rstrip('/').split('/')[-1]
        else:
            if run_name:
                name_suffixes.insert(0, run_name)
            run_name = "-".join(name_suffixes)
        if os.path.isdir(dirname):
            dirs = [os.path.realpath(os.path.join(dirname, d))
                    for d in os.listdir(dirname) if (not self._matches_patterns(d, [r'\.(FAIL|tmp)']) and
                                                     self._matches_patterns(d, job_patterns) and
                                                     os.path.isdir(os.path.join(dirname, d)) and
                                                     os.path.isfile(os.path.join(dirname, d, "clusterbuster-report.json")))]
            if not dirs:
                print(f"No matching subdirectories found under {dirname} ({arg})", sys.stderr)
                dirs = []
#                return None
            answer['dirs'] = dirs
            answer['run_name'] = run_name
        else:
            raise ValueError(f"{dirname}: Not a directory")
        return answer

    def loadFromSpecs(self, specs: list):
        answer = {
                  'metadata': {'jobs': {}},
                  'status': {'jobs': {}}
                  }
        reports = {}
        for arg in specs:
            spec = self._create_report_spec(arg)
            if spec is not None:
                if spec['run_name'] in reports:
                    raise ValueError(f'Duplicate report name {spec["run_name"]}')
                reports[spec['run_name']] = spec
        if not reports:
            raise ValueError("No reports found")
        for name, report in reports.items():
            if 'baseline' not in answer['metadata']:
                answer['metadata']['baseline'] = name
            LoadReportSet(reports[name]['dirs'], name, answer).Load()
        return answer
