#!/usr/bin/perl

use POSIX;
use strict;
use Fcntl qw(:DEFAULT O_DIRECT);
use JSON;
require "clientlib.pl";

my ($dirs, $files_per_dir, $blocksize, $block_count, $processes, $direct, $drop_cache_service, $drop_cache_port, @dirs) = parse_command_line(@ARGV);

$SIG{TERM} = sub { POSIX::_exit(0); };
my ($bufalign) = 8192;

initialize_timing();

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

sub makethem($) {
    my ($process) = @_;
    my ($ops) = 0;
    my ($buffer);
    my ($buffer) = 'a' x ($blocksize + $bufalign);
    my ($offset) = unpack('J', pack('p', $buffer)) % $bufalign;
    $offset = $bufalign - $offset;
    my ($fileargs) = O_WRONLY|O_CREAT | ($direct ? O_DIRECT : 0);
    my ($container) = container();
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
		sysopen(FILE, $filename, $fileargs, 0666) || die "Can't create file $filename: $!\n";
		$ops++;
		foreach my $block (0..$block_count - 1) {
		    if ((my $answer = syswrite(FILE, $buffer, $blocksize, $offset)) != $blocksize) {
			die "Write to $filename failed: $answer $!\n";
		    }
		    $ops++;
		}
		close FILE;
	    }
	}
    }
    return $ops;
}

sub readthem($;$) {
    my ($process, $oktofail) = @_;
    my ($ops) = 0;
    my ($buffer) = 'a' x ($blocksize + $bufalign);
    my ($offset) = unpack('J', pack('p', $buffer)) % $bufalign;
    $offset = $bufalign - $offset;
    my ($fileargs) = O_RDONLY | ($direct ? O_DIRECT : 0);
    my ($container) = container();
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
		sysopen(FILE, $filename, $fileargs) || die "Can't open file $filename: $!\n";
		$ops++;
		foreach my $block (0..$block_count - 1) {
		    if ((my $answer = sysread(FILE, $buffer, $blocksize, $offset)) != $blocksize) {
			die "Read from $filename failed: $answer $!\n";
		    }
		    $ops++;
		}
		close(FILE);
	    }
	}
    }
    return $ops;
}

sub removethem($;$) {
    my ($process, $oktofail) = @_;
    my ($ops) = 0;
    my ($container) = container();
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

sub run_one_operation($$$$$$) {
    my ($op_name0, $op_name1, $op_name2, $op_func, $process, $data_start_time) = @_;

    sync_to_controller(idname($process, "start $op_name2"));
    timestamp("$op_name0 files...");
    drop_cache($drop_cache_service, $drop_cache_port);
    my ($ucpu, $scpu) = cputimes();
    my ($op_start_time) = xtime() - $data_start_time;
    my ($ops) = &$op_func($process);
    my ($op_end_time_0) = xtime() - $data_start_time;
    drop_cache($drop_cache_service, $drop_cache_port);
    my ($op_end_time) = xtime() - $data_start_time;
    my ($op_elapsed_time) = $op_end_time - $op_start_time;
    my ($op_elapsed_time_0) = $op_end_time_0 - $op_start_time;
    my ($ucpu, $scpu) = cputimes($ucpu, $scpu);
    my (%answer) = (
	'operation_elapsed_time' => $op_elapsed_time,
	'user_cpu_time' => $ucpu,
	'system_cpu_time' => $scpu,
	'cpu_time' => $ucpu + $scpu,
	'cpu_utilization' => ($ucpu + $scpu) / $op_elapsed_time,
	'operation_start' => $op_start_time,
	'operation_end' => $op_end_time,
	'operations' => $ops,
	'operations_per_second' => $ops / $op_elapsed_time
	);
    if ($op_name2 eq 'read') {
	$answer{'total_files'} = $files_per_dir * $dirs * scalar @dirs;
	$answer{'block_count'} = int $block_count;
	$answer{'block_size'} = int $blocksize;
	$answer{'data_size'} = $blocksize * $block_count * $answer{'total_files'};
	$answer{'data_rate'} = $answer{'data_size'} / $op_elapsed_time_0;
    }
    timestamp("$op_name1 files...");
    sync_to_controller(idname($process, "end $op_name2"));
    return (\%answer, $op_start_time, $op_end_time, $ucpu, $scpu);
}

sub runit($) {
    my ($process) = @_;
    my ($iterations) = 1;
    my ($data_start_time) = xtime();
    # Make sure everything is cleared out first...but don't count the time here.
    removethem($process, 1);
    system("sync");
    my (%extras);

    my ($answer_create, $create_start_time, $create_end_time, $create_ucpu, $create_scpu) =
	run_one_operation('Creating', 'Created', 'create', \&makethem, $process, $data_start_time);
    $extras{'create'} = $answer_create;
    my ($create_et) = $create_end_time - $create_start_time;

    timestamp("Sleeping for 60 seconds");
    sleep(60);
    timestamp("Back from sleep");
    my ($answer_read, $read_start_time, $read_end_time, $read_ucpu, $read_scpu) =
	run_one_operation('Reading', 'Read', 'read', \&readthem, $process, $data_start_time);
    $extras{'read'} = $answer_read;

    timestamp("Sleeping for 60 seconds");
    sleep(60);
    timestamp("Back from sleep");
    my ($answer_remove, $remove_start_time, $remove_end_time, $remove_ucpu, $remove_scpu) =
	run_one_operation('Creating', 'Removed', 'remove', \&removethem, $process, $data_start_time);
    $extras{'remove'} = $answer_remove;
    my ($remove_et) = $remove_end_time - $remove_start_time;
    my ($data_start_time) = $create_start_time;
    my ($data_end_time) = $remove_end_time;
    my ($data_elapsed_time) = $create_et + $remove_et;
    my ($user_cpu) = $create_ucpu + $remove_ucpu;
    my ($system_cpu) = $create_scpu + $remove_scpu;
    my (%summary);
    $summary{'volumes'} = scalar @dirs;
    $summary{'dirs_per_volume'} = int $dirs;
    $summary{'total_dirs'} = $dirs * $summary{'volumes'};
    $summary{'files_per_dir'} = int $files_per_dir;
    $summary{'total_files'} = $files_per_dir * $summary{'total_dirs'};
    $summary{'blocksize'} = int $blocksize;
    $summary{'blocks_per_file'} = int $block_count;
    $summary{'filesize'} = $blocksize * $block_count;
    $summary{'data_size'} = $summary{'filesize'} * $summary{'total_files'};
    $extras{'summary'} = \%summary;
    report_results($data_start_time, $data_end_time, $data_elapsed_time,
		   $user_cpu, $system_cpu, \%extras);
}

run_workload(\&runit, $processes);
