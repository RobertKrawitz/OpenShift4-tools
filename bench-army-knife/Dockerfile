FROM docker.io/library/centos:8

COPY pbench-8.repo /etc/yum.repos.d/pbench.repo
RUN dnf install -y https://dl.fedoraproject.org/pub/epel/epel-release-latest-8.noarch.rpm && \
    dnf install -y --enablerepo PowerTools --enablerepo copr-pbench \
    fio \
    hostname \
    iproute \
    iputils \
    jq \
    openssh-clients \
    openssh-server \
    pbench-agent \
    pbench-sysstat \
    perf \
    perl \
    perl-Time-HiRes \
    procps-ng \
    rsync \
    sysbench \
    uperf && \
    dnf -y clean all
RUN mkdir -p /usr/local/bin
COPY bootstrap.sh /usr/local/bin
RUN chmod +x /usr/local/bin/bootstrap.sh
RUN sed -i -e "s/.*PermitRootLogin.*/PermitRootLogin yes  ##/" -e "s/.*Port .*/Port 2022 ##/" /etc/ssh/sshd_config && ssh-keygen -A
