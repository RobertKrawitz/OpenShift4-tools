#!/usr/bin/env python3

import os
import subprocess
import re
import json
import shutil

from clusterbuster_pod_client import clusterbuster_pod_client


class fio_client(clusterbuster_pod_client):
    """
    fio test for clusterbuster
    """

    def __init__(self):
        super().__init__()
        self.processes = int(self._args[0])
        self.rundir = self._args[1]
        self.runtime = int(self._args[2])
        self.jobfilesdir = self._args[3]
        self.drop_cache_service = self._args[4]
        self.drop_cache_port = int(self._args[5])
        self.fio_blocksizes = clusterbuster_pod_client.toSizes(self._args[6])
        self.fio_patterns = re.split(r'\s+', self._args[7])
        self.fio_iodepths = clusterbuster_pod_client.toSizes(self._args[8])
        self.fio_fdatasyncs = clusterbuster_pod_client.toBools(self._args[9])
        self.fio_directs = clusterbuster_pod_client.toBools(self._args[10])
        if self._args[11]:
            self.fio_ioengines = re.split(r'\s+', self._args[11])
        else:
            self.fio_ioengines = []
        if self._args[12]:
            self.fio_generic_args = re.split(r'\s+', self._args[12])
        else:
            self.fio_generic_args = []

    def get_token(self, pattern: str, string: str, token: int = 1):
        match = re.match(pattern, string)
        if match:
            return match.group(token)
        else:
            return None

    def prepare_data_file(self, jobfile: str):
        with open(jobfile) as job:
            lines = [line.strip() for line in job.readlines()]
            for line in lines:
                if self.get_token(r'filename\s*=\s*(.+)', line):
                    filename = self.get_token(r'\s*filename\s*=\s*(.+)', line)
                elif self.get_token(r'size\s*=\s*([0-9]+)', line):
                    filesize = int(self.get_token(r'size\s*=\s*([0-9]+)', line))
        self.timestamp(f"  Job file {filename} will be size {filesize}")
        blocksize = 2 ** 20
        blocks = int((filesize + blocksize - 1) / blocksize)
        dirname = os.path.dirname(filename)
        if not self.isdir(dirname):
            os.makedirs(dirname)
        self.timestamp("Starting file creation")
        subprocess.run(['dd', 'if=/dev/zero', f'of={filename}', f'bs={str(blocksize)}', f'count={str(blocks)}'])
        subprocess.run(['sync'])
        self.timestamp("File created")

    def runone(self, jobfile: str):
        elapsed_time = 0
        all_results = {}
        data_start_time = self.adjusted_time()
        ucpu, scpu = self.cputimes()
        jobidx = 1
        self.timestamp(f"""
Sizes:       {self._args[6]}
Patterns:    {self._args[7]}
I/O depths:  {self._args[8]}
Fdatasync:   {self._args[9]}
Direct I/O:  {self._args[10]}
I/O engines: {self._args[11]}""")
        self.timestamp("Creating workfile")
        self.prepare_data_file(jobfile)
        self.timestamp("Created workfile")
        for size in self.fio_blocksizes:
            for pattern in self.fio_patterns:
                for iodepth in self.fio_iodepths:
                    for fdatasync in self.fio_fdatasyncs:
                        for direct in self.fio_directs:
                            for ioengine in self.fio_ioengines:
                                jobname = '%04d-%s-%d-%d-%d-%d-%s' % (jobidx, pattern, size, iodepth, fdatasync, direct, ioengine)
                                self.drop_cache()
                                self.sync_to_controller(jobname)
                                if jobidx == 1:
                                    self.timestamp("Running...")
                                    data_start_time = self.adjusted_time()
                                jtime = self.adjusted_time()
                                jucpu, jscpu = self.cputimes()
                                command = ["fio", f'--rw={pattern}', f'--runtime={self.runtime}', f'--bs={size}', f'--iodepth={iodepth}', f'--fdatasync={int(fdatasync)}', f'--direct={int(direct)}', f'--ioengine={ioengine}']
                                command.extend(self.fio_generic_args)
                                command.extend(['--output-format=json+', jobfile])
                                with subprocess.Popen(command, stdout=subprocess.PIPE) as run:
                                    result = json.loads(run.stdout.read())
                                jtime = self.adjusted_time(jtime)
                                jucpu, jscpu = self.cputimes(jucpu, jscpu)
                                elapsed_time += jtime
                                job_result = {
                                    'job_elapsed_time': jtime,
                                    'job_user_cpu_time': jucpu,
                                    'job_system_cpu_time': jscpu,
                                    'job_cpu_time': jucpu + jscpu,
                                    'job_results': result
                                    }
                                all_results[jobname] = job_result
                                jobidx = jobidx + 1
        if '-IGNORE-' not in jobfile:
            data_end_time = self.adjusted_time()
            ucpu, scpu = self.cputimes(ucpu, scpu)
            extras = {
                'results': all_results
                }
            self.report_results(data_start_time, data_end_time, elapsed_time, ucpu, scpu, extras)

    def get_jobfiles(self, jobfiledir: str, tmpdir: str, localid: str):
        new_jobfiles = []
        with os.scandir(jobfiledir) as jobfiles:
            for jobfile in jobfiles:
                jobfile = f"{jobfiledir}/{jobfile.name}"
                if not self.isfile(jobfile):
                    continue
                match = re.match(r'(.*/)([^/]+)$', jobfile)
                if match:
                    nfile = f"{tmpdir}/{match.group(2)}"
                    with open(jobfile, mode='r') as infile:
                        lines = [line.strip() for line in infile.readlines()]
                        with open(nfile, mode='w') as outfile:
                            for line in lines:
                                if re.match(r'filename\s*=\s*', line):
                                    print(f'{line}/{localid}/{localid}', file=outfile)
                                else:
                                    print(line, file=outfile)
                    new_jobfiles.append(nfile)
        self.timestamp(f"get_jobfiles({jobfiledir}) => {' '.join(new_jobfiles)}")
        return new_jobfiles

    def runit(self, process: int):
        localid = self.idname(separator='-')
        localrundir = f"{self.rundir}/{localid}"
        tmp_jobsfiledir = f"/tmp/fio-{localid}.job"
        try:
            os.makedirs(tmp_jobsfiledir)
        except Exception as exc:
            self.timestamp(f"Can't create temporary jobs directory {tmp_jobsfiledir}: {exc}")
            raise(exc)
        try:
            os.makedirs(localrundir)
        except Exception as exc:
            self.timestamp(f"Can't create local run directory {localrundir}: {exc}")
            raise(exc)
        try:
            os.chdir(localrundir)
        except Exception as exc:
            self.timestamp(f"Can't cd to local run directory {localrundir}: {exc}")
            raise(exc)
        jobfiles = self.get_jobfiles(self.jobfilesdir, tmp_jobsfiledir, localid)
        if not jobfiles:
            self.timestamp("Error: no jobfiles provided!")
            return 1
        for jobfile in jobfiles:
            self.runone(jobfile)
        shutil.rmtree(self.rundir, ignore_errors=True)


fio_client().run_workload()
