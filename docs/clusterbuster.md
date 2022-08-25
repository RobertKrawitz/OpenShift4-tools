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
of the Prometheus database.  All of these outputs will be saved
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

### API

Clusterbuster has an API to interface between the tool and workloads.
Workloads are responsible for providing functions implementing these
workloads.

### Create A Workload

To create a new workload, you need to do the following:

1. Create a `.workload` file and place it in
   `lib/clusterbuster/workloads`.  The workload file is a set of bash
   functions, as the file is sourced by clusterbuster.
   
2. (Optional) Create one or more perl scripts, which go into
   `lib/clusterbuster/pod-files`.  These scripts are written in Perl
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
	  
### Create A Resource Type

Clusterbuster currently supports running workloads as pods,
ReplicaSets, or Deployments (with very minimal differences between the
latter two).  At present, the object types are hard-coded into
Clusterbuster; at some point I intend to refactor those.

All of the object types are created from `create_standard_deployment`,
which dispatches to the appropriate object creation
