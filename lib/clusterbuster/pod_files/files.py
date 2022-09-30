#!/usr/bin/env python3

import os
import time
import subprocess
import mmap
import shutil

from clusterbuster_pod_client import clusterbuster_pod_client


class files_client(clusterbuster_pod_client):
    """
    Small files test for clusterbuster
    """

    def __init__(self):
        try:
            super().__init__()
            if len(self._args) > 8:
                self.dir_list = self._args[8:]
            else:
                self.dir_list = ['/tmp']
            self.dirs = clusterbuster_pod_client._toSize(self._args[0])
            self.files_per_dir = clusterbuster_pod_client._toSize(self._args[1])
            self.blocksize = clusterbuster_pod_client._toSize(self._args[2])
            self.block_count = clusterbuster_pod_client._toSize(self._args[3])
            self._set_processes(int(self._args[4]))
            self.o_direct = clusterbuster_pod_client._toBool(self._args[5])
            self.drop_cache_service = self._args[6]
            self.drop_cache_port = int(self._args[7])
            self.flags = 0
            if self.o_direct:
                self.flags = os.O_DIRECT
        except Exception as err:
            self._abort(f"Init failed! {err} {' '.join(self._args)}")

    def remdir(self, dirname: str, oktofail: bool = False):
        try:
            os.rmdir(dirname)
        except Exception as err:
            if oktofail:
                shutil.rmtree(dirname, ignore_errors=True)
            else:
                raise err

    def makethem(self, pid: int):
        buf = mmap.mmap(-1, self.blocksize)
        buf.write(('a' * self.blocksize).encode())
        ops = 0
        try:
            for bdir in self.dir_list:
                direc = f"{bdir}/p{pid}/{self._container()}"
                os.makedirs(direc)
                ops = ops + 2
                for subdir in range(self.dirs):
                    dirname = f"{direc}/{subdir}"
                    os.mkdir(dirname)
                    ops = ops + 1
                    for fileidx in range(self.files_per_dir):
                        filename = f"{dirname}/{fileidx}"
                        fd = os.open(filename, self.flags | os.O_WRONLY | os.O_CREAT)
                        ops = ops + 1
                        for block in range(self.block_count):
                            answer = os.write(fd, buf)
                            if answer != self.blocksize:
                                raise os.IOError(f"Incomplete write to {filename}: {answer} bytes, expect {self.blocksize}")
                            ops = ops + 1
                        os.close(fd)
            return ops
        except Exception as err:
            self._timestamp(f"I/O error while creaating files: {err}")
            os._exit(1)

    def readthem(self, pid: int, oktofail: bool = False):
        ops = 0
        try:
            for bdir in self.dir_list:
                direc = f"{bdir}/p{pid}/{self._container()}"
                ops = ops + 2
                for subdir in range(self.dirs):
                    dirname = f"{direc}/{subdir}"
                    ops = ops + 1
                    for fileidx in range(self.files_per_dir):
                        filename = f"{dirname}/{fileidx}"
                        try:
                            if self.o_direct:
                                fd = os.open(filename, self.flags | os.O_RDONLY)
                                ops = ops + 1
                                for block in range(self.block_count):
                                    with mmap.mmap(fd, self.blocksize, offset=block * self.blocksize,
                                                   access=mmap.ACCESS_READ) as mm:
                                        mm.read(self.blocksize)
                                        ops = ops + 1
                                os.close(fd)
                            else:
                                with open(filename) as file:
                                    ops = ops + 1
                                    for block in range(self.block_count):
                                        file.read(self.blocksize)
                                        ops = ops + 1
                        except Exception as exc:
                            if not oktofail:
                                raise exc
            return ops
        except Exception as err:
            self._timestamp(f"I/O error while reading files: {err}")
            os._exit(1)

    def removethem(self, pid: int, oktofail: bool = False):
        ops = 0
        try:
            for bdir in self.dir_list:
                pdir = f"{bdir}/p{pid}"
                if oktofail and not self._isdir(pdir):
                    continue
                direc = f"{pdir}/{self._container()}"
                if oktofail and not self._isdir(bdir):
                    continue
                for subdir in range(self.dirs):
                    dirname = f"{direc}/{subdir}"
                    if oktofail and not self._isdir(subdir):
                        continue
                    for fileidx in range(self.files_per_dir):
                        filename = f"{dirname}/{fileidx}"
                        if oktofail and not self._isfile(filename):
                            continue
                        os.unlink(filename)
                        ops = ops + 1
                    self.remdir(dirname, oktofail)
                    ops = ops + 1
                self.remdir(direc, oktofail)
                ops = ops + 1
                self.remdir(pdir, oktofail)
                ops = ops + 1
            return ops
        except Exception as err:
            self._timestamp(f"I/O error while removing files: {err}")
            os._exit(1)

    def run_one_operation(self, op_name0: str, op_name1: str, op_name2: str, op_func, pid: int, data_start_time: float):
        self._sync_to_controller(self._idname([pid, f"start {op_name2}"]))
        self._drop_cache(self.drop_cache_service, self.drop_cache_port)
        ucpu, scpu = self._cputimes()
        op_start_time = self._adjusted_time() - data_start_time
        ops = op_func(pid)
        op_end_time_0 = self._adjusted_time() - data_start_time
        self._drop_cache(self.drop_cache_service, self.drop_cache_port)
        op_end_time = self._adjusted_time() - data_start_time
        op_elapsed_time = op_end_time - op_start_time
        op_elapsed_time_0 = op_end_time_0 - op_start_time
        ucpu, scpu = self._cputimes(ucpu, scpu)
        answer = {
            'operation_elapsed_time': op_elapsed_time,
            'user_cpu_time': ucpu,
            'system_cpu_time': scpu,
            'cpu_time': ucpu + scpu,
            'cpu_utilization': (ucpu + scpu) / op_elapsed_time,
            'operation_start': op_start_time,
            'operation_end': op_end_time,
            'operations': ops,
            'operations_per_second': ops / op_elapsed_time
            }
        if op_name2 == 'read':
            answer['total_files'] = self.files_per_dir * self.dirs * len(self.dir_list)
            answer['self.block_count'] = self.block_count
            answer['size'] = self.blocksize
            answer['data_size'] = self.blocksize * self.block_count * answer['total_files']
            answer['data_rate'] = answer['data_size'] / op_elapsed_time_0
        self._timestamp(f'{op_name1} files...')
        self._sync_to_controller(self._idname([pid, f'end {op_name2}']))
        return answer

    def runit(self, process: int):
        self.removethem(os.getpid(), True)
        data_start_time = self._adjusted_time()

        subprocess.run('sync')
        answer_create = self.run_one_operation('Creating', 'Created', 'create', self.makethem, os.getpid(), data_start_time)
        self._timestamp("Sleeping for 60 seconds")
        time.sleep(60)
        self._timestamp('Back from sleep')
        answer_read = self.run_one_operation('Reading', 'Read', 'read', self.readthem, os.getpid(), data_start_time)
        self._timestamp("Sleeping for 60 seconds")
        time.sleep(60)
        self._timestamp('Back from sleep')
        answer_remove = self.run_one_operation('Removing', 'Remove', 'remove', self.removethem, os.getpid(), data_start_time)
        create_et = answer_create['operation_end'] - answer_create['operation_start']
        # read_et = answer_read['operation_end'] - answer_read['operation_start']
        remove_et = answer_remove['operation_end'] - answer_remove['operation_start']
        data_start_time = answer_create['operation_start']
        data_end_time = answer_remove['operation_end']
        user_cpu = answer_create['user_cpu_time'] + answer_remove['user_cpu_time']
        system_cpu = answer_create['system_cpu_time'] + answer_remove['system_cpu_time']
        extras = {
            'summary': {
                'volumes': len(self.dir_list),
                'dirs_per_volume': self.dirs,
                'total_dirs': self.dirs * len(self.dir_list),
                'self.files_per_dir': self.files_per_dir,
                'total_files': self.files_per_dir * self.dirs * len(self.dir_list),
                'self.blocksize': self.blocksize,
                'blocks_per_file': self.block_count,
                'filesize': self.blocksize * self.block_count,
                'data_size': self.blocksize * self.block_count * self.files_per_dir * self.dirs * len(self.dir_list)
                },
            'create': answer_create,
            'read': answer_read,
            'remove': answer_remove
            }
        self._report_results(data_start_time, data_end_time, create_et + remove_et, user_cpu, system_cpu, extras)


files_client().run_workload()
