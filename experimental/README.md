# Experimental OpenShift4-tools

These are tools that are currently in experimental state.  I will
promote them when ready.

<!-- markdown-toc start - Don't edit this section. Run M-x markdown-toc-generate-toc again -->
**Table of Contents**

- [OpenShift4-tools](#openshift4-tools)
    - [Cluster utilities](#cluster-utilities)
    - [Testing tools](#testing-tools)
    - [General information tools](#general-information-tools)
    - [PBench orchestration](#pbench-orchestration)
    - [oinst API](#oinst-api)
        - [Introduction](#introduction)
        - [API calls](#api-calls)
        - [Validating Instance Types](#validating-instance-types)

<!-- markdown-toc end -->

## Data reporting utilities

- **prom-extract**: Capture selected Prometheus data for the duration
  of a run; report the results along with metadata and workload output
  JSON-formatted.
  
  Usage:
  
  ```
  prom-extract _options_ -- _command args..._
  ```
  
  Takes the following options:
  
  - **-u _prometheus url_**: Provide the URL to the cluster Prometheus
    server.  This normally isn't needed; the tool can find it for
    itself.
	
  - **-t _prometheus token_**: Provide the authentication token for
    the cluster Prometheus server.  This normally isn't needed.
    Currently, username/password authentication is not needed.
	
  - **-s _timestep_**: Reporting time step for metrics in seconds;
    default 30.
	
  - **-m _metrics profile_**: Profile of metrics to extract.  This is
    the same syntax as
    [Kube-Burner](https://kube-burner.readthedocs.io/en/latest/cli/)
    metrics profile sytax.  Default is `metrics.yaml` in the current
    directory.
	
  - **--epoch _relative start_**: Start the metrics collection from
    the specified period (default 1200 seconds) prior to the start of
    the job run.
	
  - **--post-settling-time _seconds_**: Continue collecting metrics
    for the specified period (default 60 seconds) after the job
    completes.
	
  - **--json-from-command**: Assume that the stdout from the command
    is well-formed JSON, and embed that JSON in the report.
	
  - **--uuid _uuid_**: Use the specified UUID as the index for the
    report.  If not provided, one is generated and reported on
    stderr.  This is useful for e. g. indexing the report into a
    database.
