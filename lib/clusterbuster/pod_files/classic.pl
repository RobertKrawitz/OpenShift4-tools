#!/usr/bin/perl

use Socket;
use POSIX;
use strict;
use Time::HiRes qw(gettimeofday usleep);
use Time::Piece;
use Sys::Hostname;
use File::Basename;
my ($dir) = $ENV{'BAK_CONFIGMAP'};
require "$dir/clientlib.pl";

my ($namespace, $container, $basetime, $baseoffset, $poddelay,
    $crtime, $exit_at_end, $synchost, $syncport, $loghost, $logport, $sleep_time) = @ARGV;
my ($start_time, $data_start_time, $data_end_time, $elapsed_time, $end_time, $user, $sys, $cuser, $csys);
$start_time = xtime();

$SIG{TERM} = sub { POSIX::_exit(0); };
$basetime += $baseoffset;
$crtime += $baseoffset;

my $pass = 0;
my $ex = 0;
my $ex2 = 0;
my ($cfail) = 0;
my ($refused) = 0;
my $time_overhead = 0;
my ($pod) = hostname;

timestamp("Clusterbuster pod starting");
my $delaytime = $basetime + $poddelay - $start_time;
if ($delaytime > 0) {
    timestamp("Sleeping $delaytime seconds to synchronize");
    usleep($delaytime * 1000000);
}
do_sync($synchost, $syncport);
my ($data_start_time) = xtime();
if ($sleep_time > 0) {
    usleep($sleep_time * 1000000);
}

my ($data_end_time) = xtime();
my ($elapsed_time) = $data_end_time - $data_start_time;
my ($user, $sys, $cuser, $csys) = times;
my ($fstring) = <<'EOF';
{
  "application": "clusterbuster-json",
  "namespace": "%s",
  "pod": "%s",
  "container": "%s",
  "process_id": %d,
  "pod_create_time_offset_from_base": %f,
  "pod_start_time_offset_from_base": %f,
  "data_start_time_offset_from_base": %f,
  "data_end_time_offset_from_base": %f,
  "data_elapsed_time": %f,
  "user_cpu_time": %f,
  "system_cpu_time": %f,
  "cpu_time": %f
}
EOF
$fstring =~ s/[ \n]+//g;
my ($results) = sprintf($fstring, $namespace, $pod, $container, $$, $crtime - $basetime,
			$start_time - $basetime, $data_start_time - $basetime,
			$data_end_time - $basetime, $elapsed_time, $user, $sys, $user + $sys);
if ($syncport) {
    do_sync($synchost, $syncport, $results);
}
if ($logport > 0) {
    do_sync($loghost, $logport, $results);
}
finish($exit_at_end);
