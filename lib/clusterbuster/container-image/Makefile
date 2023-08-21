all: $(addsuffix .image, base workloads)
workloads.image: base.image
REPO_BASE=quay.io/rkrawitz
ARCHES=amd64 arm64
TAG=latest
MANIFEST="build-clusterbuster-$*"

define NL


endef

ifneq ($(CB_REGISTRY_AUTH_FILE),)
export REGISTRY_AUTH_FILE=$(CB_REGISTRY_AUTH_FILE)
endif

%.image:
	-buildah manifest rm $(MANIFEST)
	buildah manifest create $(MANIFEST)
	$(foreach arch, $(ARCHES), buildah bud -t "$(REPO_BASE)/clusterbuster-$*:$(TAG)" --manifest $(MANIFEST) -f "Dockerfile.$*" --arch $(arch)$(NL))
	buildah manifest push --all $(MANIFEST) docker://$(REPO_BASE)/clusterbuster-$*:$(TAG)

.PHONY: %.image
