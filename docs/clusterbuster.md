# ClusterBuster

Clusterbuster is (yet another) tool for running workloads on OpenShift
clusters.  Its purpose is to simplify running workloads from the
command line and does not require external resources such as
Elasticsearch to operate.  This is written by [Robert
Krawitz](mailto:rlk@redhat.com) and is part of my OpenShift tools
package.  The main package is written in bash.

It is also intended to be fairly straightforward to add new workloads
as plugins.  Yes, it is possible to have a plugin architecture with bash!

<!-- markdown-toc start - Don't edit this section. Run M-x markdown-toc-generate-toc again -->
**Table of Contents**

- [ClusterBuster](#clusterbuster)
    - [Introduction](#introduction)
    - [Running Clusterbuster](#running-clusterbuster)
    - [Internals](#internals)
        - [Architecture](#architecture)
        - [Workloads](#workloads)
            - [Workload Host API](#workload-host-api)
            - [Workload Client (Pod) API](#workload-client-pod-api)
                - [Public Members](#public-members)
                - [Running Workloads](#running-workloads)
                - [Protected Members](#protected-members)
                - [Static methods:](#static-methods)
            - [Create A Workload](#create-a-workload)
        - [Create A Deployment Type](#create-a-deployment-type)

<!-- markdown-toc end -->

## Introduction

I started writing Clusterbuster in 2019 to simplify the process of
running scalable workloads as part of [testing to 500 pods per
node](https://cloud.redhat.com/blog/500_pods_per_node).  Since then,
it has gained new capabilities at a steady pace, and is now able to
run a variety of different workloads.

Clusterbuster monitors workloads that are running, and for most
workloads, will retrieve reporting data from them.  It can optionally
monitor metrics from Prometheus during a run and also take a snapshot
of the actual Prometheus database.  A snapshot contains the raw
Prometheus database, while metrics only contain the specific
information requested; the snapshot is much bigger and more difficult
to use, but more complete.  All of these outputs will be saved
locally; if you want to upload them to an Elasticsearch instance or
other external location, you'll currently need to make your own
arrangements.

## Running Clusterbuster

In the normal way of Linux utilities, running `clusterbuster -h`
prints a help message.  The help message is quite long, as there are a
lot of options available, but the best way of learning how to use it
is to look at one of the example files located in
`examples/clusterbuster`.  If you have access to an OpenShift cluster
with admin privileges (since it needs to create namespaces and do a
few other privileged things) Any of those files can be used via

```
clusterbuster -f <file>
```

## Internals

This section describes the architecture and internal interfaces of
Clusterbuster.

### Architecture

Todo

### Workloads

Clusterbuster supports extensible workloads.  At present, it supports
uperf, fio, many small files, CPU/startup test, and a number of others.

A workload requires, at a minimum, a workload definition in
`lib/clusterbuster/workloads`.  This is a set of bash functions that
tell clusterbuster how to deploy the workload.

Most workloads require in addition a component to run on the worker
nodes.  These are written in python.  The node components, which
reside in `lib/clusterbuster/pod_files`, are responsible for
initializing and running the workloads.  For most workloads, an
additional synchronization/control service is used to ensure that all
instances of the workload start simultaneously; the sync service also
manages distributed time and collection of results.

Finally, there are optional components for processing reports and
performing analysis of the data.  These are written in Python.

#### Workload Host API

Clusterbuster has an API to interface between the tool and workloads.
Workloads are responsible for providing functions implementing these
workloads.  The workload files are all sourced when clusterbuster
starts.  All workload files must include a callback to clusterbuster
of the form

* `register_workload name aliases...`

which defines the name of the workload and any aliases that the user
may use to invoke it (via `clusterbuster --workload=<workload>`).  The
remainder of the workload file consists of a set of functions, all of
which are named `<workload>_<api>`.  The workload file can contain
other shell functions and variables, but they should all start with
`_<workload>` (with at least one leading underscore).

Note that any global variables that workload files need must be
declared with

`declare -g <variable`

Without the `-g`, the value will not be preserved across function calls.

The following APIs are supported:

* `<workload>_document`

  Print a short documentation string to stdout; this is used to
  generate the workload-specific portion of the help.

* `<workload>_help_options`

  Print a detailed documentation string describing all supported
  command line options for the workload.  Workload-specific options
  should start with `--workload-`, but this is not enforced.  This
  function is optional, and only need be provided if the workload accepts options.

* `<workload>_process_options  option[=value] options...`

  Process options not handled by clusterbuster proper.  See one of the
  workload files for an example.  Option names have all hyphens and
  underscores stripped out, so the user can provide them as desired.
  If there are any remaining unknown options, this function should
  invoke `help` with the unknown options.  This function is optional,
  and only need be provided if the workload accepts options.

* `<workload>_supports_reporting`

  Return true (0) if the workload supports reporting, false (non-zero
  status) otherwise.

* `<workload>_list_configmaps`

  Return a list of files that must be provided to the worker object
  for the workload to run.  This consists of files in
  `lib/clusterbuster/pod_files` that are required to run the workload.

* `<workload>_list_user_configmaps`

  Return a list of other files which must be provided for the workload
  to run.  This is normally configuration files for the workload that
  are too complex to be expressed as options.

* `<workload>_calculate_logs_required  namespaces deployments replicas containers`

  Calculate how many entities are expected to provide log files and
  print that to stdout.  At present, it only matters whether this is
  zero or non-zero; if it's zero, then clusterbuster will not monitor
  the run, if it's non-zero, then clusterbuster will.

* `<workload>_create_deployment  namespace instance secret_count replicas containers_per_pod`

  Create the YAML needed to deploy the workload.  Normally this
  function will not actually generate the YAML directly; it will make
  calls back to `create_standard_deployment`.  It may make other
  calls.  See `fio.workload` and `uperf.workload` in
  `lib/clusterbuster/workloads` for examples of the callbacks that it
  may make.

* `<workload>_arglist  namespace instance secret_count replicas containers_per_pod`

  Generate the command line arguments required by the workload as a
  YAML list.  Normally, this is not done directly, but rather by
  calling back to `mk_yaml_args` to generate the necessary YAML
  fragment.  This is only required if the workload takes command line
  arguments.  Some workloads consist of multiple components, such as a
  client or server, so there may be multiple such functions named
  `<workload>_<subworkload>_arglist` corresponding to `-a` arguments
  to `create_standard_arglist`.

* `<workload>_report_options`

  Report options and their values as JSON fragments to stdout, for
  incorporation into the final report.

* `<workload>_generate_metadata`

  Report metadata for the run as a list of JSON fragments of the form

  ```
  "jobs": {
    "run_name1": metadata1,
	"run_name2": metadata2,
	...
  }
  ```
  This is not the result of the run, merely a directory of all subjobs and
  associated settings.

* `<workload>_reporting_class`

  Return the type of workload for reporting purposes.  Defaults to the
  name of the workload.  Should be used if the workload is equivalent
  to another workload for reporting purposes.
  
* `<workload>_vm_required_packages`

  Return a list of packages, one per line, that are required to run
  the workload.

* `<workload>_vm_setup_commands`

  Return a list of commands, one per line, that must be run on
  CNV/Kubevirt VMs in order to prepare for running the workload.
  Normally package requirements should be provided in
  `vm_required_packages`.

#### Workload Client (Pod) API

The Python3 API for workload pods is provided by
`lib/clusterbuster/pod_files/clusterbuster_pod_client.py`.  All
workloads should subclass this API.  The API is subject to change.
All workloads should implement a subclass of
`clusterbuster_pod_client` and invoke the `run_workload()` method of
the derived class.

```
#!/usr/bin/env python3

import time
from clusterbuster_pod_client import clusterbuster_pod_client


class minimal_client(clusterbuster_pod_client):
    """
    Minimal workload for clusterbuster
    """

    def __init__(self):
        try:
            super().__init__()
            self._set_processes(int(self._args[0]))
            self.__sleep_time = float(self._args[1])
        except Exception as err:
            self._abort(f"Init failed! {err} {' '.join(self._args)}")

    def runit(self, process: int):
        user, system = self._cputimes()
        data_start_time = self._adjusted_time()
        time.sleep(self.__sleep_time)
        user, system = self._cputimes(user, system)
        data_end_time = self._adjusted_time()
        extras = {
            'sleep_time': self.__sleep_time
            }
        self._report_results(data_start_time, data_end_time, data_end_time - data_start_time, user, system, extras)


minimal_client().run_workload()
```

##### Public Members

The `clusterbuster_pod_client` class should not be instantiated
itself; only subclasses should be instantiated.

* `clusterbuster_pod_client.run_workload(self)`

  Run an instantiated workload.  This method, once called, will not
  return.

##### Running Workloads

The `run_workload` method will call back to the `runit` method of the
subclass, passing one argument, the process number.  The
`run_workload` method will be invoked in parallel the number of times
specified by the `_set_processes()` method described below, each in a
separate subprocess.

The `runit` method should call `self._report_results` (described
below) to report the results back.  This method does not return.  If
`runit` returns without calling `self._report_results`, or raises an
uncaught exception, the workload is deemed to have failed.  Raising an
exception is the preferred way to fail a run.  It should not call
`sys.exit()` or `os.exit()` on its own; the results of that are
undefined.

##### Protected Members

This currently only documents the most commonly used members.

* /class/ `clusterbuster_pod_client.clusterbuster_pod_client(initialize_timing_if_needed: bool = True, argv: list = sys.argv)

  Initialize the `clusterbuster_pod_client` class.

  `initialize_timing_if_needed` should be `True` if the workload is
  expected to use the synchronization and control services provided by
  ClusterBuster (this is normally the case).  It should only be `False`
  if the workload will not synchronize.  This is most commonly the
  case if the workload is part of a composite workload that does not
  need to synchronize independently, such as the server side of a
  client-server workload.

  `argv` is normally the command line arguments.  You should never
  need to provide anything else.  Arguments not consumed by the
  `clusterbuster_pod_client` are provided in the
  `self._args` variable, as a list.  The constructor will only be
  called once (as opposed to the `runit` method).

  If the /constructor/ needs to report an error, it should call
  `self.abort() with an error message rather than exiting.

* `clusterbuster_pod_client._set_processes(self, processes: int = 1)`

  Specify how many workload processes are to be run.  It is not
  necessary to call this if you intend for only one instance of the
  workload to run.

* `clusterbuster_pod_client._cputimes(self, olduser: float = 0, oldsys: float = 0)`

  Return a tuple of <user, system> cputime accrued by the process.  If
  non-zero cputimes are provided as arguments, they will be subtracted
  from the returned cputimes; this allows for convenient start/stop
  timing.  This includes both self time and child time.

* `clusterbuster_pod_client._cputime(self, otime: float = 0)`

  Return the total CPU time accrued by the process.  If a non-zero
  time value is provided, it is subtracted from the measured CPU time.

* `clusterbuster_pod_client._adjusted_time(self, otime: float = 0)`

  Return the wall clock time as a float, synchronized with the host.
  This should be used in preference to `time.time()`.  If a non-zero
  `otime` is provided, it returns the interval since that time.

* `clusterbuster_pod_client._timestamp(self, string)`

  Prints a message to stderr, with a timestamp prepended.  This is the
  preferred way to log a message.

* `clusterbuster_pod_client._report_results(self, data_start_time: float, data_end_time: float, data_elapsed_time: float, user_cpu: float, sys_cpu: float, extra: dict = None)`

  Report results at the end of a run.  This should always be called
  out of `runit()` unless `runit` raises an exception.  This method is
  likely to change in the future.

  `data_start_time` is the time that the job as a whole started work,
  as returned by `_adjusted_time()`.  It may not be the moment at
  which `_runit()` gets control, if that routine needs to perform
  preliminary setup or synchronize.

  `data_end_time` is the time that the job as a whole completed work,
  as returned by `_adjusted_time()`.

  `data_elapsed_time` is the total time spent running.  It may not be
  the same as `data_end_time - data_start_time` if the workload
  consists of multiple steps with synchronization or other
  setup/teardown required between them.

  `user_cpu` is the amount of user CPU time consumed by the workload;
  it may not be the total accrued CPU time of the process.  `sys_cpu`
  is similar.

  `extra` is any additional data, as a dictionary, that the workload
  wants to log.

* `clusterbuster_pod_client._sync_to_controller(self, token: str = None)`

  Synchronize to the controller.  The number of times that the
  workload needs to synchronize should be computed on the host side;
  the pod side needs to ensure that it only synchronizes the desired
  number of times.  If `token` is not provided, one will be generated.

* `clusterbuster_pod_client._idname(self, args: list = None, separator: str = ':')`

  Generate an identifier based on namespace, pod name, container name,
  and process ID along with any other tokens desired by the workload.
  If a separator is provided, it is used to separate the tokens.

* `clusterbuster_pod_client._podname(self)`
  `clusterbuster_pod_client._container(self)`
  `clusterbuster_pod_client._namespace(self)`

  Return the pod name (equivalent to the hostname of the pod), the
  container name, and the namespace of the pod respectively.

* `clusterbuster_pod_client._listen(self, port: int = None, addr: str = None, sock: socket = None, backlog=5)`

  Listen  on  the  specified  port  and  optionally  address.   As  an
  alternate option, an existing socket  may be provided; in this case,
  port and  addr must  both be  None.  If  `backlog` is  provided, the
  listener will listen with the specified queue length.

* `clusterbuster_pod_client._connect_to(self, addr: str = None, port: int = None, timeout: float=None)`

  Connect to the specified address on the specified port.  If a
  timeout is provided, it will time out after at least that long;
  otherwise it will not time out.

* `clusterbuster_pod_client._resolve_host(self, hostname: str)`

  Resolve a DNS hostname.  This is not normally needed, as
  `_connect_to` will do what is needed.  This will retry as needed
  until it succeeds.

* `clusterbuster_pod_client._toSize(self, arg: str)`
  `clusterbuster_pod_client._toSizes(self, *args)`

  Convert an argument to a size (non-negative integer).  Sizes can be
  decimal numbers, or numbers with a suffix of 'k', 'm', 'g', or 't'
  respectively to represent thousands, millions, billions, or
  trillions.  If the suffix has a further suffix of `i`, it is treated
  as binary (powers of 1024) rather than decimal (powers of 1000).

  If the argument is an integer or float, it is returned as an
  integer.

  If it cannot be parsed as an integer, a ValueError is raised.

  The `toSizes()` takes any of the following:

  * Integer or float: the value returned as an integer
  * String: the string is comma- and space-split, and each component
    is converted as described above.
  * List: each element of the list is treated according to the
    preceding rules.

  These methods are useful for parsing argument lists.

* `clusterbuster_pod_client._toBool(self, arg: str, defval: bool = None)`
  `clusterbuster_pod_client._toBools(self, *args)`

  Convert an argument to a Boolean.  The argument can be any of the
  following:

  * Boolean, integer, float, list, or dict: the Python rules for
    conversion to Boolean are used.
  * String (all case-insensitive:
    * `true`, `y`, `yes`: True
    * `false`, `n`, `no`: False
	* Can be converted to an integer: 0 is False, anything else is True
  * Anything else (including a string that cannot be converted as
    above): if `defval` is provided, it is used; if not, a ValueError
    is raised.

  The `toBools` method works the same way as `toSizes`.  This method
  cannot accept a default value.

  These methods are useful for parsing argument lists.

* `clusterbuster_pod_client._splitStr(self, regexp: str, arg: str)`

  Split `arg` into a list of strings per the provided `regexp`.  It
  differs from `re.split()` in that this routine returns an empty list
  if an empty string is passed; `re.split()` returns a list of a
  single element.


#### Create A Workload

To create a new workload, you need to do the following:

1. Create a `.workload` file and place it in
   `lib/clusterbuster/workloads`.  The workload file is a set of bash
   functions, as the file is sourced by clusterbuster.

2. (Optional) Create one or more workloads, which go into
   `lib/clusterbuster/pod_files`.  These are the actual workloads, or
   scripts that run them.  These are written in Python and are
   subclasses of `clusterbuster_pod_client`.

3. (Optional) Create Python scripts to generate reports.  If you don't
   do this and attempt to generate a report, you'll get only a generic
   report which won't have any workload-specific information.  You can
   create any of the following scripts, but each type of script
   requires the one before it.

   1. *reporter*: a reporter script is responsible for parsing the
      JSON data created by your workload and producing basic reports
      without analysis.  All existing workloads that report have
      reporter scripts.

   2. *loader*: a loader script is responsible for loading a JSON
      report and creating a data structure suitable for further
      analysis.  At present, only selected workloads have loaders.

   3. *analysis*: analysis scripts transform the loaded data into a
      form suitable for downstream consumption, be it by humans,
      databases, or spreadsheets.  There are several types of analysis
      scripts, and more may be added in the future.  That's Todo.

### Create A Deployment Type

Clusterbuster currently supports running workloads as pods,
ReplicaSets, or Deployments (with very minimal differences between the
latter two).  At present, the object types are hard-coded into
Clusterbuster; at some point I intend to refactor those.

All of the object types are created from `create_standard_deployment`,
which dispatches to the appropriate object creation based on the value
of `deployment_type` (currently either `create_pod_deployment` or
`create_replication_deployment`).  Both of these create similar
specifications using `create_spec`; other types of objects will
probably be quite similar.  However, VMs will likely be rather
different and may need more customization of the code.

## Bring Your Own Workload

It is possible (although at present somewhat complicated) to use your
own workload without writing a full Python wrapper for it, by means of
the `byo` workload.  The Clusterbuster arguments are described in the
help message.

The workload command needs to accept an argument `--setup` as the
first and only option to indicate that any setup should be done at
this point, such as creating files, cloning repos, etc.

The command, along with any other files specified by the user by means
of `--byo-file` arguments, is placed in the working directory
specified by `--byo-workload` or a default location if not specified.
The working directory is writable.

The command should produce valid JSON (or empty output) on its stdout,
which is incorporated into the report generated by Clusterbuster.  All
other output should be to stderr.

There are two commands that can be used from the workload:

* `do-sync` synchronizes between all of the instances (pods,
  containers, and top level processes) comprising the workload.  All
  instances should call `do-sync` the same number of times throughout
  the run, and any subprocesses created by the workload command should
  not call `do-sync`.

* `drop-cache` may be used to drop the buffer cache, but can only
  usefully be used if `--byo-drop-cache=1` is used on the
  Clusterbuster command line.  If you do use this, it is suggested
  that you call `do-sync` following `drop-cache`, but it is not
  mandatory.
  
When called in setup, the command should not use either `do-sync` or
`drop-cache`.

The command can discover location information about itself by means of
the `CB_PODNAME`, `CB_CONTAINER`, and `CB_NAMESPACE` environment
variables.  In addition `CB_INDEX` contains the index number (not the
process ID) of the process for multiple processes in a container, and
`CB_ID` contains an identification string that may be used as an
identifier in JSON output.

An example workload command is located in
`examples/clusterbuster/byo/cpusoaker-byo.sh`.
