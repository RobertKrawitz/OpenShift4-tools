.PHONY: base workloads

all: base workloads
workloads: base
MANIFEST=build-clusterbuster
MANIFEST_WORKLOADS=build-clusterbuster-workloads
ARCHES=amd64 arm64

ifneq ($(CB_REGISTRY_AUTH_FILE),)
export REGISTRY_AUTH_FILE=$(CB_REGISTRY_AUTH_FILE)
endif

base:
	-buildah manifest rm "$(MANIFEST)"
	buildah manifest create "$(MANIFEST)"
	buildah bud -t quay.io/rkrawitz/clusterbuster:latest --manifest "$(MANIFEST)" -f Dockerfile --arch amd64 .
	buildah bud -t quay.io/rkrawitz/clusterbuster:latest --manifest "$(MANIFEST)" -f Dockerfile --arch arm64 .
	buildah manifest push --all "$(MANIFEST)" docker://quay.io/rkrawitz/clusterbuster:latest

workloads:
	-buildah manifest rm "$(MANIFEST_WORKLOADS)"
	buildah manifest create "$(MANIFEST_WORKLOADS)"
	buildah bud -t quay.io/rkrawitz/clusterbuster-workloads:latest --manifest "$(MANIFEST_WORKLOADS)" -f Dockerfile.workloads --arch amd64 .
	buildah bud -t quay.io/rkrawitz/clusterbuster-workloads:latest --manifest "$(MANIFEST_WORKLOADS)" -f Dockerfile.workloads --arch arm64 .
	buildah manifest push --all "$(MANIFEST_WORKLOADS)" docker://quay.io/rkrawitz/clusterbuster-workloads:latest
