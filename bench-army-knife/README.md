# bench-army-knife

*WIP*

<!-- markdown-toc start - Don't edit this section. Run M-x markdown-toc-generate-toc again -->
**Table of Contents**

- [bench-army-knife](#bench-army-knife)
    - [Components of bench-army-knife](#components-of-bench-army-knife)
        - [bench-army-knife controller](#bench-army-knife-controller)
        - [bench-army-knife agent](#bench-army-knife-agent)

<!-- markdown-toc end -->


bench-army-knife is a way to orchestrate
[PBench](https://distributed-system-analysis.github.io/pbench/) under
OpenShift or Kubernetes.  It uses a container image layered on the
[PBench images](https://quay.io/organization/pbench), specifically the
`pbench-agent-all-centos-8` image, to run the PBench controller and
agents.  The image can be used independently of PBench as a convenient
way to run workloads.

The key advantages of `bench-army-knife` as a PBench orchestration
tool are:

- By containerizing the controller, it avoids any need to install
  anything on the host system.
  
- By containerizing the agents, it avoids any need to modify the node
  installation such as running an ssh server on a custom port.  Agents
  can run either privileged or non-privileged; running non-privileged
  reduces the amount of data that can be collected, but the container
  will run.  One privilege needs to be granted to the agent container,
  but it does not require full system privilege.  Some workloads may
  require additional privileges, but they would at least implicitly
  require the same privileges running in other environments.
  
- In addition, the containerized agents allow running agents within a
  VM if a virtualized pod is used in addition to running agents in
  ordinary pods on the nodes.

- By not requiring ssh from the controller to the agents, it allows
  running PBench on a cluster without opening inbound ports and
  knowing the IP addresses of the worker nodes and pods up front.
  
The main disadvantage of `bench-army-knife` is that it's still a bit
more complicated to use than other deployment solutions.

As noted, PBench does not require the ability to ssh from the pbench
controller to the pbench agents.  It is, however, required to be able
to ssh _from_ the agents to the bench-army-knife controller.  This
allows the bench-army-knife agents to open an ssh tunnel to the
bench-army-knife controller, which the pbench controller can then use
to ssh back to the pbench agents running inside the bench-army-knife
agents.  The [Tool
Meister](https://github.com/distributed-system-analysis/pbench/pull/1248)
orchestration in PBench 0.69 reduces the need for ssh, but does not at
present completely eliminate the need to ssh from the controller to
the workers.  Bench-army-knife does eliminate that, at least insofar
as any configuration is required.

As also noted above, bench-army-knife also provides a way to run
PBench agents either within worker pods or standalone on worker nodes,
or both.  The latter is useful if one is running a workload inside a
VM under OpenShift, allowing capture of information both from the node
(host) and the pod (running inside the guest).  It's also useful for
running workloads involving multiple pods per node, when the overhead
of multiple agents is not desirable; where the workload is an existing
OpenShift workload that can't use the bench-army-knife image; or if
it's important that the workload not run privileged.

There are two major components to bench-army-knife, the controller and
the agent.  These two components wrap the pbench controller and agent
respectively, orchestrating the pbench control flow.

## Components of bench-army-knife

Bench-army-knife uses a similar controller-agent approach as PBench
does; indeed, the bench-army-knife controller runs the components used
with PBench controllers and the bench-army-knife agent runs a PBench
agent internally.

I may rename the two components, likely to "journeyman" and
"apprentice", to avoid confusion with the PBench terminology.

### bench-army-knife controller

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

### bench-army-knife agent

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

## Operation of bench-army-knife

The basic operational workflow of bench-army-knife is described here.
It assumes understanding of basic Kubernetes application creation,
secrets and configmaps, networking (in particular ports), and the use
of affinity/anti-affinity if additional standalone bench-army-knife
agents need to be deployed.

### User Operations

1. The application creates a service exposing two ports that will be
   used to communicate from the bench-army-knife agent to the
   bench-army-knife controller, one for control flow and another for
   ssh from the agent to the controller.  With Tool Meister, a third
   port will need to be created for the Redis server that will be
   running alongside the controller.
   
2. The application creates a secret that contains, at a minimum, the
   PBench server key and configuration needed for the PBench
   controller and agents to communicate with the PBench server, and a
   key pair for the bench-army-knife agents and controller to mutually
   communicate.  This key pair can be generated on a session basis;
   it's not necessary for it to be persistent.  This secret needs to
   be mounted in 
   
3. The application workload pods and any additional standalone
   bench-army-knife pods (or deployment or similar) are created.  If a
   standalone bench-army-knife deployment needs to be created, it
   should be done at this time too.
   
   The bench-army-knife agent pods (including the application pods)
   should be invoked with a particular calling sequence and command
   line arguments as described below.
   
4. The application creates a bench-army-knife controller.  The
   controller (either pod, standalone container, or on a host) needs
   to be invoked with a specific calling sequence as described below.
   
#### Invoking workload pods

#### Invoking standalone bench-army-knife Agents

#### Invoking the bench-army-knife Controllers

### Internal Operation

For the purposes of this section, "agent" refers to the
bench-army-knife agent and "controller" similarly refers to the
bench-army-knife controller, unless otherwise stated.

1. The agent is started in a container with the address/hostname and
   sync port of the controller, in addition to keys needed to contact
   the controller and the pbench server.

2. On start, the agent creates a local-only sshd, listening on an
   arbitrary port.  The sshd is actually invoked via a perl script
   that opens the port and hands it off to the sshd.
   
3. The agent contacts the controller with with a random token and
   hostname for the agent.  The hostname does not need to be the real
   hostname; it's simply used as an identifier.  The agent does not
   time out contacting the controller.
   
4. The controller spawns an sshd to accept connections from the
   agents.  This sshd uses a custom config file populated with
   hostname and the associated controller port.  The port is later
   used by the agent when it creates the tunnel as described above.

5. The controller optionally spawns an sshd to accept connections from
   the agents, using a shared key.
   
6. The controller listens for a defined number of connections from
   agents.  When all of the agents have connected, the controller
   replies to the agents with the port to connect to and the desired
   tunnel port for each agent.
   
   This is done synchronously to simplify later stages in the protocol
   (when the agent will wait for the controller to complete).
   
7. When the agents receive the connection information from the
   controller, they create ssh tunnels (via ssh -R) to the controller,
   and then attempt to contact the controller again on the sync port,
   again waiting forever for a response.
   
8. The controller attempts to ping each agent in turn via ssh on its
   tunnel port, waiting up to 60 seconds for the agents to connect and
   establish the tunnel.

9. After all agents have been successfully contacted, the controller
   performs typical pbench controller actions:
   
   * `pbench-register/tool-set` / `pbench-register-tool` or other tool
     script (that will presumably run some combination of such
     commands) as passed in.
	 
   * Run the desired benchmark.  This can be any pbench-<*benchmark*>
     script, or arguments to `pbench-user-benchmark`.
