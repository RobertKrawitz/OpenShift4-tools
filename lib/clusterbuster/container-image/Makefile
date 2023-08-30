.PHONY: %.image %.containerdisk FORCE

all: $(addsuffix .image, base workloads vm)
workloads.image: base.image

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

# Container information (assumes Fedora)
FEDORA_VERSION=38
FEDORA_IMAGE_TYPE=Cloud
URL_FILE_VERSION=38-1.6

URL_BASE:=http://download.fedoraproject.org/pub/fedora/linux/releases
URL_STEM=$(URL_BASE)/$(FEDORA_VERSION)/$(FEDORA_IMAGE_TYPE)/__ARCH__/images
IMAGE_BASE=Fedora-$(FEDORA_IMAGE_TYPE)-Base-$(URL_FILE_VERSION)
FEDORA_URL_TEMPLATE=$(URL_STEM)/$(IMAGE_BASE).__ARCH__.qcow2
FEDORA_IMAGE = $(subst __ARCH__,$($*_ARCH_REV),$(FEDORA_URL_TEMPLATE))

MANIFEST="build-clusterbuster-$*"

define NL


endef

ifneq ($(CB_REGISTRY_AUTH_FILE),)
export REGISTRY_AUTH_FILE=$(CB_REGISTRY_AUTH_FILE)
endif

vm_deps = $(foreach arch, $(ARCHES), $(FEDORA_IMAGE))
base_deps := FORCE
workloads_deps := FORCE

vm.image:: $(addsuffix .containerdisk, $(ARCHES))

%.image:
	-buildah manifest rm $(MANIFEST)
	buildah manifest create $(MANIFEST)
	$(foreach arch, $(ARCHES), buildah  --build-arg ARCH=$(arch) bud -t "$(REPO_BASE)/clusterbuster-$*:$(TAG)" --manifest $(MANIFEST) -f "Dockerfile.$*" --arch $(arch)$(NL))
	buildah manifest push --all $(MANIFEST) docker://$(REPO_BASE)/clusterbuster-$*:$(TAG)

$(IMAGE_BASE).%.qcow2:
	wget $(FEDORA_IMAGE)

%.containerdisk:
ifeq ($(FEDORA_IMAGE),)
	-echo "Unknown architecture $*"
	false
endif
	echo $*
	$(MAKE) $(notdir $(FEDORA_IMAGE))
	-virsh destroy cnv-containerdisk
	-virsh undefine --nvram cnv-containerdisk
	-rm -f base-image-$*x.qcow2
	cp -p $(notdir $(FEDORA_IMAGE)) base-image-$*x.qcow2
	virt-customize -a base-image-$*x.qcow2 --firstboot firstboot.vm
	virt-install --disk base-image-$*x.qcow2 --import --name=cnv-containerdisk --graphics=none --virt-type=qemu --network default --os-variant=fedora37 --arch=$($*_ARCH_REV) --boot=hd
	-virsh destroy cnv-containerdisk
	-virsh undefine cnv-containerdisk

FORCE: ;
