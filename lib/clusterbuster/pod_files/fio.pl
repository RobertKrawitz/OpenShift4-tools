#!/usr/bin/perl

use Socket;
use POSIX;
use strict;
use Time::Piece;
use Time::HiRes qw(gettimeofday usleep);
use File::Path qw(make_path remove_tree);
use Sys::Hostname;
use File::Basename;
my ($dir) = $ENV{'BAK_CONFIGMAP'};
require "$dir/clientlib.pl";

our ($namespace, $container, $basetime, $baseoffset, $poddelay, $crtime, $exit_at_end, $synchost, $syncport, $loghost, $logport, $processes, $rundir, $runtime, $jobfiles_dir, $fio_generic_args) = @ARGV;

my ($data_start_time, $data_end_time);
$SIG{TERM} = sub() { docleanup() };
$basetime += $baseoffset;
$crtime += $baseoffset;
my ($start_time) = xtime();

my ($pod) = hostname;
my ($localrundir) = "$rundir/$pod/$$";

sub removeRundir() {
    if (-d "$localrundir") {
	open(CLEANUP, "-|", "rm -rf '$localrundir'");
	while (<CLEANUP>) {
	    1;
	}
	close(CLEANUP);
    }
}

sub docleanup()  {
    removeRundir();
    kill 'KILL', -1;
    POSIX::_exit(0);
}

removeRundir();

if (! make_path($localrundir)) {
    timestamp("Cannot create run directory $localrundir: $!");
}
if (! chdir($localrundir)) {
    timestamp("Cannot cd $localrundir: $!");
    exit(1);
}

sub runit(;$) {
    my ($jobfile) = @_;
    my ($firsttime) = 1;
    my ($avgcpu) = 0;
    my ($weight) = .25;
    my ($icputime);
    my ($interval) = 5;
    my ($dstime) = xtime();

    my $delaytime = $basetime + $poddelay - $dstime;
    if ($delaytime > 0) {
	timestamp("Sleeping $delaytime seconds to synchronize");
	usleep($delaytime * 1000000);
    }
    do_sync($synchost, $syncport);
    my ($ucpu0, $scpu0) = cputime();
    my ($answer0) = '';
    timestamp("Running...");
    my ($data_start_time) = xtime();
    timestamp("fio $fio_generic_args --output-format=json+ $jobfile");
    open(RUN, "-|", "fio $fio_generic_args --output-format=json+ $jobfile | jq -c .") || die "Can't run fio: $!\n";
    while (<RUN>) {
	$answer0 .= "$_";
    }
    close(RUN);
    my ($data_end_time) = xtime();
    my ($ucpu1, $scpu1) = cputime();
    $ucpu1 -= $ucpu0;
    $scpu1 -= $scpu0;
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
  "cpu_time": %f,
  "results": %s
}
EOF
    $fstring =~ s/[ \n]+//g;
    my ($answer) = sprintf($fstring, $namespace, $pod, $container, $$, $crtime - $basetime,
			   $start_time - $basetime, $data_start_time - $basetime,
			   $data_end_time - $basetime, $data_end_time - $data_start_time,
			   $ucpu1, $scpu1, $ucpu1 + $scpu1,
			   $answer0 eq '' ? '{}' : $answer0);

    do_sync($synchost, $syncport, $answer);
    if ($logport > 0) {
	do_sync($loghost, $logport, $answer);
    }
}

sub get_jobfiles($) {
    my ($dir) = @_;
    opendir DIR, $dir || die "Can't find job files in $dir: #!\n";

    my @files = map { "$dir/$_" } grep { -f "$dir/$_" } sort readdir DIR;
    closedir DIR;
    print STDERR "get_jobfiles($dir) => @files\n";
    return @files;
}

my (@jobfiles) = get_jobfiles($jobfiles_dir);

sub runall() {
    if ($#jobfiles >= 0) {
	foreach my $file (@jobfiles) {
	    runit($file)
	}
    } else {
        runit()
    }
}

if ($processes > 1) {
    for (my $i = 0; $i < $processes; $i++) {
        if ((my $child = fork()) == 0) {
            runall();
	    docleanup();
            exit(0);
        }
    }
} else {
    runall();
}
if ($exit_at_end) {
    timestamp("About to exit");
    while (wait() > 0) {}
    timestamp("Done waiting");
    print STDERR "FINIS\n";
    POSIX::_exit(0);
} else {
    timestamp("Waiting forever");
    pause()
}
EOF
