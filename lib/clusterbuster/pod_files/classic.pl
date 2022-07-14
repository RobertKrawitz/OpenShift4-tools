#!/usr/bin/perl

use Socket;
use POSIX;
use strict;
use Time::HiRes qw(gettimeofday usleep);
use Time::Piece;
use Sys::Hostname;
use File::Basename;
use Getopt::Long;
Getopt::Long::Configure('bundling', 'no_ignore_case', 'pass_through');
my ($dir) = $ENV{'BAK_CONFIGMAP'};
require "$dir/clientlib.pl";

my ($namespace, $container, $basetime, $baseoffset,
    $crtime, $exit_at_end, $synchost, $syncport, $loghost, $logport, $sleep_time);
GetOptions('n=s' => \$namespace,
	   'namespace=s' => \$namespace,
	   'c=s' => \$container,
	   'container=s' => \$container,
	   'basetime=f' => \$basetime,
	   'baseoffset=f' => \$baseoffset,
	   'crtime=f' => \$crtime,
	   'exit_at_end!' => \$exit_at_end,
	   'synchost=s' => \$synchost,
	   'sync_host=s' => \$synchost,
	   'syncport=i' => \$syncport,
	   'sync_port=i' => \$syncport,
	   'loghost=s' => \$loghost,
	   'log_host=s' => \$loghost,
	   'logport=i' => \$logport,
	   'log_port=i' => \$logport,
	   'run_time=f' => \$sleep_time,
	   'runtime=f' => \$sleep_time,
    );

my ($start_time, $data_start_time, $data_end_time, $elapsed_time, $end_time, $user, $sys, $cuser, $csys);
my ($start_time) = xtime();

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
initialize_timing($basetime, $crtime, $synchost, $syncport,
		  "$namespace:$pod:$container", $start_time);
$start_time = get_timing_parameter('start_time');

timestamp("Clusterbuster pod starting");
my ($data_start_time) = xtime();
if ($sleep_time > 0) {
    usleep($sleep_time * 1000000);
}

my ($data_end_time) = xtime();
my ($elapsed_time) = $data_end_time - $data_start_time;
my ($user, $sys, $cuser, $csys) = times;
my ($results) = print_json_report($namespace, $pod, $container, $$,
				  $data_start_time, $data_end_time,
				  $data_end_time - $data_start_time,
				  $user, $sys);
timestamp("RESULTS $results");
if ($syncport) {
    do_sync($synchost, $syncport, $results);
}
if ($logport > 0) {
    do_sync($loghost, $logport, $results);
}
finish($exit_at_end);
