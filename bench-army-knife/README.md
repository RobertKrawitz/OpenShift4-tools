# bench-army-knife

*WIP*

<!-- markdown-toc start - Don't edit this section. Run M-x markdown-toc-generate-toc again -->
**Table of Contents**

- [bench-army-knife](#bench-army-knife)
    - [bench-army-knife controller](#bench-army-knife-controller)
    - [bench-army-knife agent](#bench-army-knife-agent)

<!-- markdown-toc end -->


bench-army-knife is a way to orchestrate
[PBench](https://github.com/distributed-system-analysis/pbench) under
OpenShift or Kubernetes.  It provides a way to run workloads under
PBench without any requirement to ssh from the pbench controller to
pbench agents.  The only requirement is to be able to ssh from the
agents to the bench-army-knife controller (which runs the pbench
controller).  This is done by having the agents ssh to the
bench-army-knife controller to open a tunnel back to the agent by
means of customizing the ssh configuration.  The Tool Meister
orchestration in PBench at present does not completely eliminate the
need to ssh to the agents; bench-army-knife does.

This also provides a way to run PBench agents either within worker
pods or standalone on worker nodes, or both.  The latter is useful if
one is running a workload inside a VM under OpenShift, allowing
capture of information both from the node (host) and the pod (running
inside the guest).  It's also useful for running workloads involving
multiple pods per node, when the overhead of multiple agents is not
desirable; where the workload is an existing OpenShift workload that
can't use the bench-army-knife image; or if it's important that the
workload not run privileged.

There are two major components to bench-army-knife, the controller and
the agent.  These two components wrap the pbench controller and agent
respectively, orchestrating the pbench control flow.

## bench-army-knife controller

The function of the bench-army-knife controller is to accept
connections from bench-army-knife agents, establish ssh tunnels to
allow the pbench controller to connect to the pbench agents running
inside the bench-army-knife agents, and perform the usual sequence of
registering tools, running benchmarks, and moving results to the
desired pbench server.

The bench-army-knife controller can be run either outside the cluster
or in a separate pod inside the cluster, although it is normally
preferred to run it inside a container as it needs to modify the
filesystem in small ways.  The bench-army-knife controller listens for
the desired number of connections from agents and runs
`pbench-register-tool` and/or `pbench-register-tool-set` followed by
the workload, and when everything is complete runs
`pbench-move-results` to save away the data.

The controller makes the following modifications to the filesystem:

1) Optionally replaces /opt/pbench-agent/config/pbench-agent.cfg with
a customized one.

2) Adds /opt/pbench-agent/id_rsa if it does not already exist (needed
because the pbench-agent hard codes this).

3) Adds authorized keys for the agent to $HOME/.ssh/authorized_keys
unless a local ssh server is used.

4) Creates a tmpdir in $HOME for purpose of ssh.

## bench-army-knife agent

The function of the bench-army-knife agent is to connect to the
bench-army-knife controller, establish a reverse ssh tunnel to allow
the pbench controller inside the bench-army-knife controller to create
and manage pbench agents inside the bench-army-knife agent container.
This is always run in a container.  The bench-army-knife agent
container may also run the desired benchmark workload, or it may run
standalone to allow collecting node level data in addition to pod
level data.  This is useful, for example, if the pods are running
inside VMs and it is desired to instrument the VM in addition to the
pod.

The agent is typically run as a privileged pod, but that isn't
absolutely necessary.  Running non-privileged will limit collection of
some data, such as pidstat for processes not owned by the user, but
much of the common data will still be collected.
