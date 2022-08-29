#!/usr/bin/perl
use Socket;
use POSIX;
use strict;
use Time::Piece;
use Time::HiRes qw(gettimeofday usleep);
use Sys::Hostname;
use File::Basename;
my ($dir) = $ENV{'BAK_CONFIGMAP'};
require "$dir/clientlib.pl";

$SIG{TERM} = sub { POSIX::_exit(0); };
my ($namespace, $container, $basetime, $baseoffset, $crtime,
    $exit_at_end, $synchost, $syncport, $listen_port) = @ARGV;
$basetime += $baseoffset;
my ($pod) = hostname;
my ($processes) = 1;

sub runit() {
    timestamp("Starting uperf server on port $listen_port");
    system("uperf", "-s", "-v", "-P", "$listen_port");
    timestamp("Done!");
}

my (%pids) = ();
for (my $i = 0; $i < $processes; $i++) {
    my $child;
    if (($child = fork()) == 0) {
	runit();
	exit(0);
    } else {
	$pids{$child} = 1;
    }
}
while (%pids) {
    my ($child) = wait();
    if ($child == -1) {
	finish($exit_at_end);
    } elsif (defined $pids{$child}) {
	if ($?) {
	    timestamp("Pid $child returned status $?!");
	    finish($exit_at_end, $?, $namespace, $pod, $container, $synchost, $syncport, $child);
	}
	delete $pids{$child};
    }
}

finish($exit_at_end);
