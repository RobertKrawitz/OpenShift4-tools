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

- [OpenShift4-tools](#openshift4-tools)
    - [Cluster utilities](#cluster-utilities)
    - [Testing tools](#testing-tools)
    - [Data reporting utilities](#data-reporting-utilities)
    - [General information tools](#general-information-tools)
    - [PBench orchestration](#pbench-orchestration)
    - [oinst API](#oinst-api)
        - [Introduction](#introduction)
        - [API calls](#api-calls)
        - [Validating Instance Types](#validating-instance-types)

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
nodes.  These components are written in perl, although I'm considering
writing a python binding too.  The node components, which reside in
`lib/clusterbuster/pod_files`, are responsible for initializing and
running the workloads.  For most workloads, an additional
synchronization/control service is used to ensure that all instances
of the workload start simultaneously; the sync service also manages
distributed time and collection of results.

Finally, there are optional components for processing reports and
performing analysis of the data.  These are written in Python.

#### Workload API

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
  for the workload to run.  This consists of Perl files in
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

#### Create A Workload

To create a new workload, you need to do the following:

1. Create a `.workload` file and place it in
   `lib/clusterbuster/workloads`.  The workload file is a set of bash
   functions, as the file is sourced by clusterbuster.

2. (Optional) Create one or more perl scripts, which go into
   `lib/clusterbuster/pod_files`.  These scripts are written in Perl
   (sorry!) and are responsible for running workloads.  Documenting
   them is Todo.

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
