#!/usr/bin/perl

use POSIX;
use strict;
my ($dir) = $ENV{'BAK_CONFIGMAP'};
require "$dir/clientlib.pl";

$SIG{TERM} = sub { POSIX::_exit(0); };
my ($listen_port) = parse_command_line(@ARGV);

sub runit() {
    timestamp("Starting uperf server on port $listen_port");
    system("uperf", "-s", "-v", "-P", "$listen_port");
    timestamp("Done!");
}

run_workload(1, \&runit);
