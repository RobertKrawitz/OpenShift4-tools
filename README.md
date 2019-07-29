# OpenShift4-tools

My tools for installing etc. OpenShift 4.

- *oinst*: OpenShift 4.x installer wrapper.

  You may want to install kubechart
  (github.com/sjenning/kubechart/kubechart) and oschart
  (github.com/sjenning/oschart/oschart) to monitor the cluster as it
  boots and runs.

- *bastion-ssh* and *bastion-scp* -- use an ssh bastion to access
   cluster nodes.
   
- *openshift-release-info* -- get various information about one or
  more releases.

- *clean-cluster*: clean up a libvirt cluster if
  `openshift-install destroy cluster` doesn't work.
  
- *waitfor-pod*: wait for a specified pod to make its appearance
  
- *get-first-master*: find the external IP address first master node of
  a cluster.

- *get-masters*: get the external IP addresses of all of the master
  nodes of a cluster.

- *get-nodes*: get the external (if available) or internal IP address
  of each node in a cluster.

- *get-container-status*: retrieve the status of each running
  container on the cluster.
  
- *get-images*: retrieve the image and version of each image used by
  the cluster.

- *bounce-cluster-kubelet*: replace the kubelet (hyperkube) on the
  master nodes and restart it.

- *install-kubelet*: helper for bounce-cluster-kubelet.
