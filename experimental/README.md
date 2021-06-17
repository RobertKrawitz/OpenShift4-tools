# Experimental OpenShift4-tools

These are tools that are currently in experimental state.  I will
promote them when ready.

<!-- markdown-toc start - Don't edit this section. Run M-x markdown-toc-generate-toc again -->
**Table of Contents**

- [Experimental OpenShift4-tools](#experimental-openshift4-tools)
    - [Data reporting utilities](#data-reporting-utilities)

<!-- markdown-toc end -->

## Data reporting utilities

- **prom-extract**: Capture selected Prometheus data for the duration
  of a run; report the results along with metadata and workload output
  JSON-formatted.

  `prom-extract` is written in Python.  It requires the following
  Python3 libraries to be installed:

  - **python3-pyyaml**: available via dnf/yum on Fedora, RHEL, etc.

  - **prometheus-api-client**: not currently packaged.  This can be
    installed via `pip3 install prometheus-api-client`.  *Note that
    this is **not** the same package as `prometheus-client`, which is
    available via dnf*.  `prometheus-api-client` provides the
    Prometheus query API, while `prometheus-client` is a Prometheus
    provider.

  - **openshift-client**: not currently packaged.  This can be
    installed via `pip3 install openshift-client`.  It provides much
    of the OpenShift client API.

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

	If the JSON output contains a key named `results`, it will be
    copied into a `results` key in the report; otherwise the entire
    JSON contents will be copied into `results`.

	If the JSON output contains a key named `api_objects`, these will
    be copied into the report.  `api_objects` should be a list of
    entries, each of which contains keys `name`, `kind`, and
    `namespace`.  These objects should be in existence after the job
    exits, so that they can be queried via the equivalent of `oc get
    -ojson ...`.  Pods have abbreviated data included; other objects
    are fully included.  These resources are not deleted.

	Any remaining objects in the JSON output are copied into a
    `run_data` key.

  - **--uuid _uuid_**: Use the specified UUID as the index for the
    report.  If not provided, one is generated and reported on
    stderr.  This is useful for e. g. indexing the report into a
    database.
