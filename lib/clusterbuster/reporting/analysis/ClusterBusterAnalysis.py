#!/usr/bin/env python3
# Copyright 2022-2023 Robert Krawitz/Red Hat
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

import sys
import importlib
import inspect
import argparse
from ..reporting_exceptions import ClusterBusterReportingException


class ClusterBusterAnalysisException(ClusterBusterReportingException):
    def __init__(self, *args):
        super().__init__(args)


class ClusterBusterAnalysisIncompatibleReportTypes(ClusterBusterAnalysisException):
    def __init__(self, workload, report_type, you):
        super().__init__("Incompatible report types for %s: expect %s, found %s" %
                         (workload, report_type, you.__class__.__name__))


class ClusterBusterAnalysisBadReportType(ClusterBusterAnalysisException):
    def __init__(self, report_type):
        super().__init__("Unexpected report type %s, expect either str or dict" %
                         (report_type.__name__))


class ClusterBusterAnalysisImportFailed(ClusterBusterAnalysisException):
    def __init__(self, report_type, exc):
        super().__init__(f"Failed to import module {report_type}: {exc}")


class ClusterBusterAnalyzeOne:
    def __init__(self, workload: str, data: dict, metadata: dict):
        self._workload = workload
        self._data = data
        self._metadata = metadata

    def _safe_get(self, obj, keys: list, default=None):
        try:
            while keys:
                key = keys[0]
                obj = obj[key]
                keys = keys[1:]
            return obj
        except (KeyboardInterrupt, BrokenPipeError):
            sys.exit()
        except KeyError:
            return default

    def Analyze(self):
        pass


class ClusterBusterAnalysisBase:
    def __init__(self):
        pass

    def job_status_vars(self):
        return ['result', 'job_start', 'job_end', 'job_runtime']

    def job_metadata_vars(self):
        return ['uuid', 'run_host', 'openshift_version', 'kata_containers_version', 'kata_version', 'cnv_version']


class ClusterBusterPostprocessBase(ClusterBusterAnalysisBase):
    def __init__(self, report, status, metadata, extras=None):
        self._report = report
        self._status = status
        self._metadata = metadata
        self._extra_args = extras


class ClusterBusterAnalysis(ClusterBusterAnalysisBase):
    """
    Analyze ClusterBuster reports
    """
    def __init__(self, data: dict, report_type=None, extras=None):
        super().__init__()
        self._data = data
        self._extras = extras
        parser = argparse.ArgumentParser(description="ClusterBuster loader")
        parser.add_argument('--allow-mismatch', action='store_true')
        self._args, self._extra_args = parser.parse_known_args(extras)
        if report_type is None:
            report_type = 'ci'
        self._report_type = report_type

    @staticmethod
    def list_analysis_formats():
        return ['ci', 'spreadsheet', 'summary', 'raw']

    def __postprocess(self, report, status, metadata):
        import_module = None
        try:
            imported_lib = importlib.import_module(f'..{self._report_type}.analyze_postprocess', __name__)
            for i in inspect.getmembers(imported_lib):
                if i[0] == 'AnalyzePostprocess':
                    import_module = i[1]
                    break
        except (SyntaxError, ModuleNotFoundError):
            pass
        if import_module is not None:
            try:
                return import_module(report, status, metadata, extras=self._extras).Postprocess()
            except TypeError as exc:
                raise ClusterBusterAnalysisImportFailed(self._report_type, exc) from None
        else:
            return report

    def Analyze(self):
        report = dict()
        metadata = dict()
        status = dict()
        if self._data is None:
            return None
        report_type = None
        if 'metadata' in self._data:
            metadata = self._data['metadata']
        if 'status' in self._data:
            status = self._data['status']
        if self._report_type == 'raw':
            return self._data
        for workload, workload_data in sorted(self._data.items()):
            if workload == 'metadata' or workload == 'status':
                continue
            failed_load = False
            load_failed_exception = None
            try:
                imported_lib = importlib.import_module(f'..{self._report_type}.{workload}_analysis', __name__)
            except (KeyboardInterrupt, BrokenPipeError):
                sys.exit(0)
            except (SyntaxError, ModuleNotFoundError) as exc:
                if isinstance(exc, ModuleNotFoundError) and exc.name.endswith(f"{workload}_analysis"):
                    print(f'Warning: no analyzer for workload {workload}', file=sys.stderr)
                    continue
                else:
                    raise type(exc)('%s reporter: %s: %s' % (workload, exc.__class__.__name__, exc)) from None
            except Exception as exc:
                print(f'Warning: no analyzer for workload {workload} {exc}', file=sys.stderr)
                continue
            if failed_load:
                raise type(load_failed_exception)
            try:
                for i in inspect.getmembers(imported_lib):
                    if i[0] == f'{workload}_analysis':
                        report[workload] = i[1](workload, workload_data, metadata).Analyze()
                        if report_type is None:
                            report_type = type(report[workload])
                        elif not isinstance(report[workload], report_type):
                            raise ClusterBusterAnalysisIncompatibleReportTypes(workload, report_type, report[workload])
            except (KeyboardInterrupt, BrokenPipeError):
                sys.exit()
            except Exception as exc:
                raise exc from None
        if report_type == str:
            return self.__postprocess('\n\n'.join([str(v) for v in report.values()]), status, metadata)
        elif report_type == dict or report_type == list:
            report['metadata'] = metadata
            for v in self.job_metadata_vars():
                if v in metadata:
                    report['metadata'][v] = metadata[v]
            for v in self.job_status_vars():
                if v in status:
                    report['metadata'][v] = status[v]
            if 'failed' in status and len(status['failed']) > 0:
                report['metadata']['failed'] = status['failed']
            return self.__postprocess(report, status, metadata)
        elif report_type is None:
            return None
        else:
            raise ClusterBusterAnalysisBadReportType(report_type)
