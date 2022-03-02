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

our ($namespace, $container, $basetime, $baseoffset, $poddelay, $crtime, $sync_host, $sync_port, $log_host, $log_port, $dirs, $files_per_dir, $blocksize, $block_count, $processes, @dirs) = @ARGV;
my ($start_time, $elapsed_time, $end_time, $user, $sys, $cuser, $csys);

$SIG{TERM} = sub { POSIX::_exit(0); };
$basetime += $baseoffset;
$crtime += $baseoffset;
$start_time = xtime();

my ($pod) = hostname;

if ($#dirs < 0) {
    @dirs=("/tmp");
}

sub remdir($$) {
    my ($dirname, $oktofail) = @_;
    if (! rmdir("$dirname")) {
	if ($oktofail) {
	    system("rm", "-rf", "$dirname");
	} else {
	    rmdir("$dirname") || die("Can't remove directory $dirname: $!\n");
	}
    }
}

sub removethem($;$) {
    my ($process, $oktofail) = @_;
    my ($ops) = 0;
    foreach my $bdir (@dirs) {
	my ($pdir)="$bdir/p$process";
	next if ($oktofail && ! -d $pdir);
	my ($dir)="$pdir/$container";
	next if ($oktofail && ! -d $dir);
	foreach my $subdir (0..$dirs-1) {
	    my ($dirname) = "$dir/d$subdir";
	    next if ($oktofail && ! -d $dirname);
	    foreach my $file (0..$files_per_dir-1) {
		my ($filename) = "$dirname/f$file";
		next if ($oktofail && ! -f $filename);
		unlink($filename) || die "Can't remove $filename: $!\n";
		$ops++;
	    }
	    remdir($dirname, $oktofail);
	    $ops++;
	}
	remdir("$dir", $oktofail);
	$ops++;
	remdir("$pdir", $oktofail);
	$ops++;
    }
    return $ops;
}

sub makethem($) {
    my ($process) = @_;
    my ($ops) = 0;
    my ($buffer);
    vec($buffer, $blocksize - 1, 8) = "A";
    foreach my $bdir (@dirs) {
	my ($pdir)="$bdir/p$process";
	mkdir("$pdir") || die("Can't create directory $pdir: $!\n");
	$ops++;
	my ($dir)="$pdir/$container";
	mkdir("$dir") || die("Can't create directory $dir: $!\n");
	$ops++;
	foreach my $subdir (0..$dirs-1) {
	    my ($dirname) = "$dir/d$subdir";
	    mkdir("$dirname") || die("Can't create directory $dirname: $!\n");
	    $ops++;
	    foreach my $file (0..$files_per_dir-1) {
		my ($filename) = "$dirname/f$file";
		open(FILE, ">", $filename) || die "Can't create file $filename: $!\n";
		$ops++;
		foreach my $block (0..$block_count - 1) {
		    if (syswrite(FILE, $buffer, $blocksize) != $blocksize) {
			die "Write to $filename failed: $!\n";
		    }
		    $ops++;
		}
		close FILE;
	    }
	}
    }
    return $ops;
}

sub run_one_operation($$$$$$$) {
    my ($op_name0, $op_name1, $op_name2, $op_func, $sync_host, $sync_port, $process) = @_;
    my ($op_format_string) = <<'EOF';
"%s": {
  "operation_elapsed_time": %f,
  "user_cpu_time": %f,
  "system_cpu_time": %f,
  "cpu_time": %f,
  "cpu_utilization": %f,
  "operation_start_time_offset_from_base": %f,
  "operation_end_time_offset_from_base": %f,
  "operations": %d,
  "operations_per_second": %f
}
EOF
    $op_format_string =~ s/[ \n]+//g;

    do_sync($sync_host, $sync_port);
    timestamp("$op_name0 files...");
    my ($ucpu0, $scpu0) = cputime();
    my ($op_start_time) = xtime() - $basetime;
    my ($ops) = &$op_func($process);
    system("sync");
    my ($op_end_time) = xtime() - $basetime;
    my ($op_elapsed_time) = $op_end_time - $op_start_time;
    my ($ucpu1, $scpu1) = cputime();
    $ucpu1 -= $ucpu0;
    $scpu1 -= $scpu0;
    my ($answer) = sprintf($op_format_string, $op_name2, $op_elapsed_time,
			   $ucpu1, $scpu1, $ucpu1 + $scpu1, ($ucpu1 + $scpu1) / $op_elapsed_time,
			   $op_start_time, $op_end_time,
			   $ops, $ops / $op_elapsed_time);
    timestamp("$op_name1 files...");
    do_sync($sync_host, $sync_port);
    return ($answer, $op_start_time, $op_end_time, $ucpu1, $scpu1);
}

sub runit($) {
    my ($process) = @_;
    my ($basecpu) = cputime();
    my ($prevcpu) = $basecpu;
    my ($iterations) = 1;

    my $delaytime = $basetime + $poddelay - $start_time;
    if ($delaytime > 0) {
	timestamp("Sleeping $delaytime seconds to synchronize");
	usleep($delaytime * 1000000);
    }
    # Make sure everything is cleared out first...but don't count the time here.
    removethem($process, 1);
    system("sync");

    my ($answer_create, $create_start_time, $create_end_time, $create_ucpu, $create_scpu) =
	run_one_operation('Creating', 'Created', 'create', \&makethem,
			  $sync_host, $sync_port, $process);
    my ($create_et) = $create_end_time - $create_start_time;

    timestamp("Sleeping for 60 seconds");
    sleep(60);
    timestamp("Back from sleep");
    my ($answer_remove, $remove_start_time, $remove_end_time, $remove_ucpu, $remove_scpu) =
	run_one_operation('Creating', 'Removed', 'remove', \&removethem,
			  $sync_host, $sync_port, $process);
    my ($remove_et) = $remove_end_time - $remove_start_time;
    my ($data_start_time) = $create_start_time;
    my ($data_end_time) = $remove_end_time;
    my ($data_elapsed_time) = $create_et + $remove_et;
    my ($user_cpu) = $create_ucpu + $remove_ucpu;
    my ($system_cpu) = $create_scpu + $remove_scpu;

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
  "block_count": %d,
  "block_size": %d,
%s,
%s
}
EOF
    my ($answer) = sprintf($fstring, $namespace, $pod, $container, $$, $crtime - $basetime,
			   $start_time - $basetime, $data_start_time, $data_end_time,
			   $data_elapsed_time, $user_cpu, $system_cpu, $user_cpu + $system_cpu, $block_count, $blocksize,
			   $answer_create, $answer_remove);
    $answer =~ s/[ \n]+//g;
    timestamp("$answer");
    do_sync($sync_host, $sync_port, "$answer");
    if ($log_port > 0) {
	do_sync($log_host, $log_port, "$answer");
    }
}

timestamp("Filebuster client starting");
$SIG{CHLD} = 'IGNORE';
if ($processes > 1) {
    for (my $i = 0; $i < $processes; $i++) {
        if ((my $child = fork()) == 0) {
            runit($i);
            exit(0);
        }
    }
} else {
    runit(0);
}
finish();
