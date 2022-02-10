#!/usr/bin/perl

use Socket;
use POSIX;
use strict;
use Time::Piece;
use Time::HiRes qw(gettimeofday usleep);
use Sys::Hostname;
#use File::Sync qw(sync);
our ($namespace, $container, $basetime, $baseoffset, $poddelay, $crtime, $sync_host, $sync_port, $log_host, $log_port, $dirs, $files_per_dir, $blocksize, $block_count, $processes, @dirs) = @ARGV;
my ($start_time, $data_start_time, $data_end_time, $elapsed_time, $end_time, $user, $sys, $cuser, $csys);
$SIG{TERM} = sub { POSIX::_exit(0); };
$basetime += $baseoffset;
$crtime += $baseoffset;
$start_time = xtime();

my ($pod) = hostname;

sub cputime() {
    my (@times) = times();
    my ($usercpu) = $times[0] + $times[2];
    my ($syscpu) = $times[1] + $times[3];
    return ($usercpu, $syscpu);
}

sub ts() {
    my (@now) = gettimeofday();
    return sprintf("%s.%06d", gmtime($now[0])->strftime("%Y-%m-%dT%T"), $now[1]);
}
sub timestamp($) {
    my ($str) = @_;
    printf STDERR "%7d %s %s\n", $$, ts(), $str;
}
sub xtime() {
    my (@now) = gettimeofday();
    return $now[0] + ($now[1] / 1000000.0);
}

sub connect_to($$) {
    my ($addr, $port) = @_;
    my ($connected) = 0;
    my ($ghbn_time, $stime);
    my ($fname,$faliases,$ftype,$flen,$faddr);
    my ($sock);
    do {
        ($fname,$faliases,$ftype,$flen,$faddr) = gethostbyname($addr);
        my $sockaddr = "S n a4 x8";
        if (length($faddr) < 4) {
            print STDERR "Malformed address, waiting for addr for $addr\n";
            sleep(1);
        } else {
            my $straddr = inet_ntoa($faddr);
            $ghbn_time = xtime();
            my $sockmeta = pack($sockaddr, AF_INET, $port, $faddr);
            socket($sock, AF_INET, SOCK_STREAM, getprotobyname('tcp')) || die "can't make socket: $!";
            $stime = xtime();
            if (connect($sock, $sockmeta)) {
                $connected = 1;
                timestamp("Connected to $addr:$port ($fname, $ftype), waiting for sync");
            } else {
                close $sock;
                sleep(1);
            }
        }
    } while (! $connected);
    return ($sock);
}

sub do_sync($$;$) {
    my ($addr, $port, $token) = @_;
    if (not $addr) { return; }
    if ($addr eq '-') {
	$addr=`ip route get 1 |awk '{print \$(NF-2); exit}'`;
	chomp $addr;
    }
    if ($token && $token =~ /clusterbuster-json/) {
	$token =~ s,\n *,,g;
    } elsif (not $token) {
        $token = sprintf('%s-%d', $pod, rand() * 999999999);
    }
    while (1) {
	timestamp("Waiting for sync on $addr:$port");
	my ($_conn) = connect_to($addr, $port);
	my ($sbuf);
	timestamp("Writing token $token to sync");
	my ($answer) = syswrite($_conn, $token, length $token);
	if ($answer != length $token) {
	    timestamp("Write token failed: $!");
	    exit(1);
	}
	$answer = sysread($_conn, $sbuf, 1024);
	my ($str) = sprintf("Got sync (%s, %d, %s)!", $answer, length $sbuf, $!);
	if ($!) {
	    timestamp("$str, retrying");
	} else {
	    timestamp("$str, got sync");
	    return;
        }
    }
}

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
    my ($op_start_time) = xtime();
    my ($ops) = &$op_func($process);
    system("sync");
    my ($op_end_time) = xtime();
    my ($op_elapsed_time) = $op_end_time - $op_start_time;
    my ($ucpu1, $scpu1) = cputime();
    $ucpu1 -= $ucpu0;
    $scpu1 -= $scpu0;
    my ($answer) = sprintf($op_format_string, $op_name2, $op_elapsed_time,
			   $ucpu1, $scpu1, $ucpu1 + $scpu1, ($ucpu1 + $scpu1) / $op_elapsed_time,
			   $op_start_time - $basetime, $op_end_time - $basetime,
			   $ops, $ops / $op_elapsed_time);
    timestamp("$op_name1 files...");
    do_sync($sync_host, $sync_port);
    return ($answer, $op_elapsed_time, $ucpu1, $scpu1);
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

    my ($data_start_time) = xtime();
    my ($answer_create, $create_et, $create_ucpu, $create_scpu) =
	run_one_operation('Creating', 'Created', 'create', \&makethem,
			  $sync_host, $sync_port, $process);

    timestamp("Sleeping for 60 seconds");
    sleep(60);
    timestamp("Back from sleep");
    my ($answer_remove, $remove_et, $remove_ucpu, $remove_scpu) =
	run_one_operation('Creating', 'Removed', 'remove', \&removethem,
			  $sync_host, $sync_port, $process);
    my ($data_end_time) = xtime();
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
			   $start_time - $basetime, $data_start_time - $basetime, $data_end_time - $basetime,
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
print STDERR "FINIS\n";
timestamp("Waiting for all processes to exit...");
while (wait() > 0) {}
timestamp("Done waiting");
POSIX::_exit(0);
