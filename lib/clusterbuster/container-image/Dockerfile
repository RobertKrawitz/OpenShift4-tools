FROM quay.io/fedora/fedora-minimal:latest

RUN microdnf --setopt=install_weak_deps=0 install -y \
    fio \
    fio-engine-libaio \
    python3 \
    sysbench \
    uperf && \
    microdnf -y clean all && \
    rm -rf /var/cache/yum
