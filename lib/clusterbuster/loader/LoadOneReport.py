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


class LoadOneReport:
    def __init__(self, report: dict, answer: dict):
        try:
            self._report = report
            self._answer = answer
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
            answer['metadata']['openshift_version'] = self._metadata['kubernetes_version'].get('openshiftVersion', 'Unknown')
            answer['metadata']['run_host'] = self._metadata['runHost']
            answer['metadata']['kata_version'] = self._metadata.get('kata_version', None)
            answer['metadata']['cnv_version'] = self._metadata.get('cnv_version', None)
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
        if 'runtime_class' in self._metadata:
            self._runtime_env = self._metadata['runtime_class']
        else:
            self._runtime_env = 'runc'
        answer['metadata']['runtime_class'] = self._runtime_env
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
