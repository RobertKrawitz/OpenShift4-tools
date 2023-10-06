.PHONY: %.image %.containerdisk FORCE

all: $(addsuffix .image, base workloads vm)
ifeq ($(NOBASEDEP),)
workloads.image: base.image
endif

# Image repo information
REPO_BASE=quay.io/rkrawitz
TAG=latest
# Container image architecture names
ARCHES=amd64 arm64

# Mapping between architecture names (differ between container
# images and Linux machine names).
x86_64_ARCH=amd64
aarch64_ARCH=arm64
amd64_ARCH=amd64
arm64_ARCH=arm64
amd64_ARCH_REV=x86_64
arm64_ARCH_REV=aarch64
x86_64_ARCH_REV=x86_64
aarch64_ARCH_REV=aarch64

# Default does not pass through enough CPU flags to be x86_64_v2, which is neeeded
# for CentOS-Stream9
amd64_QEMU_FLAGS=--arch=x86_64 --qemu-commandline='-cpu Skylake-Client'
x86_64_QEMU_FLAGS=$(amd64_QEMU_FLAGS)
arm64_QEMU_FLAGS=--arch=aarch64
aarch64_QEMU_FLAGS=$(arm64_QEMU_FLAGS)


DIST = CENTOS

# Container information (assumes Fedora)
FEDORA_VERSION=38
FEDORA_IMAGE_TYPE=Cloud
FEDORA_URL_FILE_VERSION=38-1.6

FEDORA_URL_BASE:=http://download.fedoraproject.org/pub/fedora/linux/releases
FEDORA_URL_STEM=$(FEDORA_URL_BASE)/$(FEDORA_VERSION)/$(FEDORA_IMAGE_TYPE)/__ARCH__/images
FEDORA_IMAGE_BASE=Fedora-$(FEDORA_IMAGE_TYPE)-Base-$(FEDORA_URL_FILE_VERSION)
FEDORA_CONTAINER_IAMGE=quay.io/fedora/fedora-minimal:latest
FEDORA_OS_VARIANT=fedora37

# Container information (assumes CentOS Stream)
CENTOS_VERSION=9
CENTOS_IMAGE_TYPE=GenericCloud
CENTOS_URL_FILE_VERSION=latest

CENTOS_URL_BASE=https://cloud.centos.org/centos
CENTOS_URL_STEM=$(CENTOS_URL_BASE)/$(CENTOS_VERSION)-stream/__ARCH__/images
CENTOS_IMAGE_BASE=CentOS-Stream-$(CENTOS_IMAGE_TYPE)-$(CENTOS_VERSION)-$(CENTOS_URL_FILE_VERSION)
CENTOS_CONTAINER_IMAGE=quay.io/centos/centos:stream$(CENTOS_VERSION)-minimal
CENTOS_OS_VARIANT=centos-stream$(CENTOS_VERSION)

# Container image (generic)

URL_TEMPLATE=$($(DIST)_URL_STEM)/$($(DIST)_IMAGE_BASE).__ARCH__.qcow2
# This is a bit tricky.  It relies on this only being used within the
# %.containerdisk rule, so $* will be set correctly.
IMAGE=$(subst __ARCH__,$($*_ARCH_REV),$(URL_TEMPLATE))
IMAGE_BASE=$(notdir $(IMAGE))
OS_VARIANT=$($(DIST)_OS_VARIANT)

MANIFEST="build-clusterbuster-$*"

define NL


endef

ifneq ($(CB_REGISTRY_AUTH_FILE),)
export REGISTRY_AUTH_FILE=$(CB_REGISTRY_AUTH_FILE)
endif

vm_deps = $(foreach arch, $(ARCHES), $(IMAGE))
base_deps := FORCE
workloads_deps := FORCE

vm.image:: $(addsuffix .containerdisk, $(ARCHES))

%.image:
	-buildah manifest rm $(MANIFEST)
	buildah manifest create $(MANIFEST)
	$(foreach arch, $(ARCHES), buildah  --build-arg ARCH=$(arch) --build-arg CONTAINER_IMAGE=$($(DIST)_CONTAINER_IMAGE) bud -t "$(REPO_BASE)/clusterbuster-$*:$(TAG)" --manifest $(MANIFEST) -f "Dockerfile.$*" --arch $(arch)$(NL))
	buildah manifest push --all $(MANIFEST) docker://$(REPO_BASE)/clusterbuster-$*:$(TAG)

%.qcow2:
	wget $(REMOTE)

%.containerdisk:
ifeq ($(IMAGE),)
	-echo "Unknown architecture $*"
	false
endif
	$(MAKE) $(IMAGE_BASE) REMOTE=$(IMAGE)
	-virsh destroy cnv-containerdisk
	-virsh undefine --nvram cnv-containerdisk
	-rm -f base-image-$*x.qcow2
	cp -p $(IMAGE_BASE) base-image-$*x.qcow2
	virt-customize -a base-image-$*x.qcow2 --firstboot firstboot.vm
	virt-install --disk base-image-$*x.qcow2 --import --name=cnv-containerdisk --graphics=none --virt-type=qemu --network default --os-variant=$(OS_VARIANT) $($*_QEMU_FLAGS) --boot=hd
	-virsh destroy cnv-containerdisk
	-virsh undefine cnv-containerdisk

FORCE: ;
