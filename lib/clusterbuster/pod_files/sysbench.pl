#!/usr/bin/perl

use Socket;
use POSIX;
use strict;
use Time::Piece;
use Time::HiRes qw(gettimeofday);
use File::Path qw(make_path remove_tree);
use Sys::Hostname;
our ($namespace, $container, $basetime, $baseoffset, $crtime, $poddelay, $processes, $rundir, $runtime, $exit_at_end, $synchost, $syncport, $loghost, $logport, $sysbench_generic_args, $sysbench_cmd, $sysbench_fileio_args, $sysbench_modes) = @ARGV;
my ($pod) = hostname;
my ($localrundir) = "$rundir/$pod/$$";

my ($start_time) = xtime();

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
    print STDERR "CLEANUP\n";
    removeRundir();
    kill 'KILL', -1;
    POSIX::_exit(0);
}
$SIG{TERM} = sub() { docleanup() };
$basetime += $baseoffset;
$crtime += $baseoffset;

sub cputime() {
    my (@times) = times();
    return ($times[0] + $times[2], $times[1] + $times[3]);
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
            timestamp("Connecting to $addr:$port ($fname, $ftype)");
            $ghbn_time = xtime();
            my $sockmeta = pack($sockaddr, AF_INET, $port, $faddr);
            socket($sock, AF_INET, SOCK_STREAM, getprotobyname('tcp')) || die "can't make socket: $!";
            $stime = xtime();
            if (connect($sock, $sockmeta)) {
                $connected = 1;
                timestamp("Connected to $addr:$port ($fname, $ftype), waiting for sync");
            } else {
                timestamp("Could not connect to $addr on port $port: $!");
                close $sock;
                sleep(1);
            }
        }
    } while (! $connected);
    return ($sock, $ghbn_time, $stime);
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
	my ($sync_conn, $i1, $i2) = connect_to($addr, $port);
	my ($sbuf);
	timestamp("Writing token $token to sync");
	my ($answer) = syswrite($sync_conn, $token, length $token);
	if ($answer != length $token) {
	    timestamp("Write token failed: $!");
	    exit(1);
	}
	$answer = sysread($sync_conn, $sbuf, 1024);
	my ($str) = sprintf("Got sync (%s, %d, %s)!", $answer, length $sbuf, $!);
	if ($!) {
	    timestamp("$str, retrying");
	} else {
	    timestamp("$str, got sync");
	    return;
        }
    }
}

my (%units_multiplier) = (
    'kb'  => 1000,
    'kib' => 1024,
    'mb'  => 1000 * 1000,
    'mib' => 1024 * 1024,
    'gb'  => 1000 * 1000 * 1000,
    'gib' => 1024 * 1024 * 1024,
    'tb'  => 1000 * 1000 * 1000 * 1000,
    'tib' => 1024 * 1024 * 1024 * 1024,
    );

sub runit() {
    my ($files) = 0;
    my ($totalbytes) = 0;
    my ($seconds) = 0;
    my ($rate) = 0;
    my ($et) = 0;
    my (@known_sysbench_fileio_modes) = qw(seqwr seqrewr seqrd rndrd rndwr rndrw);
    my ($iterations) = 0;
    my ($loops_per_iteration) = 10000;
    if ($sysbench_modes) {
        @known_sysbench_fileio_modes = split(/ +/, $sysbench_modes);
    }
    timestamp(join("|", @known_sysbench_fileio_modes));
    removeRundir();
    if (! make_path($localrundir)) {
        timestamp("Cannot create run directory $localrundir: $!");
	exit(1);
    }
    if (! chdir($localrundir)) {
        timestamp("Cannot cd $localrundir: $!");
	exit(1);
    }
    my (@op_answers) = ();
    my ($op_answer_fstring) = <<'EOF';
"%s": {
  "read_ops": %d,
  "write_ops": %d,
  "fsync_ops": %d,
  "read_rate_mb_sec": %d,
  "write_rate_mb_sec": %d,
  "elapsed_time": %d,
  "min_latency_sec": %f,
  "mean_latency_sec": %f,
  "max_latency_sec": %f,
  "p95_latency_sec": %f,
  "files": %d,
  "filesize": %d,
  "blocksize": %d,
  "rdwr_ratio": %f,
  "fsync_frequency": %d,
  "final_fsync_enabled": "%s",
  "io_mode": "%s",
  "user_cpu_time": %f,
  "sys_cpu_time": %f
}
EOF
    my ($firsttime) = 1;
    my ($avgcpu) = 0;
    my ($weight) = .25;
    my ($icputime);
    my ($interval) = 5;
    my $data_start_time = xtime();

    my $delaytime = $basetime + $poddelay - $start_time;
    if ($delaytime > 0) {
	timestamp("Sleeping $delaytime seconds to synchronize");
	usleep($delaytime * 1000000);
    }
    my ($base0_user, $base0_sys) = cputime();
    foreach my $mode (@known_sysbench_fileio_modes) {
	do_sync($synchost, $syncport);
	timestamp("Preparing...");
	timestamp("sysbench --time=$runtime $sysbench_generic_args $sysbench_cmd prepare --file-test-mode=$mode $sysbench_fileio_args");
	open(PREPARE, "-|", "sysbench --time=$runtime $sysbench_generic_args $sysbench_cmd prepare --file-test-mode=$mode $sysbench_fileio_args") || die "Can't run sysbench: $!\n";
	while (<PREPARE>) {
	    if ($_ =~ /^([[:digit:]]+) bytes written in ([[:digit:].]+) seconds/) {
		$totalbytes = $1;
		$seconds = $2;
		$rate = $1 / $2;
	    } elsif ($_ =~ /^Creating file /) {
		$files++;
		next;
	    }
	    if ($ENV{"VERBOSE"} > 0) {
		chomp;
		timestamp($_);
	    }
	}
	close PREPARE;

	do_sync($synchost, $syncport);
	my ($op0_user, $op0_sys) = cputime();
	timestamp("Running...");
	timestamp("sysbench --time=$runtime $sysbench_generic_args $sysbench_cmd run --file-test-mode=$mode $sysbench_fileio_args");
	open(RUN, "-|", "sysbench --time=$runtime $sysbench_generic_args $sysbench_cmd run --file-test-mode=$mode $sysbench_fileio_args") || die "Can't run sysbench: $!\n";
	my ($files) = 0;
	my ($filesize) = 0;
	my ($blocksize) = 0;
	my ($rdwr_ratio) = 1.0;
	my ($fsync_frequency) = 0;
	my ($final_fsync_enabled) = 'Disabled';
	my ($io_mode) = 'unknown';
	my ($readops) = 0;
	my ($writeops) = 0;
	my ($fsyncops) = 0;
	my ($readrate) = 0;
	my ($writerate) = 0;
	my ($min_lat) = 0;
	my ($avg_lat) = 0;
	my ($max_lat) = 0;
	my ($p95_lat) = 0;
	while (<RUN>) {
	    if      ($_ =~ m;^[[:space:]]*([[:digit:]]+) *files, *([[:digit:]]+)([KMGT]i?B);) {
		$files = $1;
		$filesize = $2 * (defined $units_multiplier{lc $3} ? $units_multiplier{lc $3} : 1);
	    } elsif ($_ =~ m;^[[:space:]]*Block size *([[:digit:]]+)([KMGT]i?B);) {
		$blocksize = $1 * (defined $units_multiplier{lc $2} ? $units_multiplier{lc $2} : 1);
	    } elsif ($_ =~ m;^[[:space:]]*Read/Write ratio for combined random IO test: *([[:digit:]]+(\.[[:digit:]]+)?);) {
		$rdwr_ratio = $1 * 1.0;
	    } elsif ($_ =~ m;^[[:space:]]*Periodic FSYNC enabled, calling fsync\(\) each ([[:digit:]]+);) {
		$fsync_frequency = $1;
	    } elsif ($_ =~ m;^[[:space:]]*calling fsync\(\) at the end of test, (enabled|disabled);i) {
		$final_fsync_enabled = $1;
	    } elsif ($_ =~ m;^[[:space:]]*Using (.*) I/O mode;) {
		$io_mode = $1;
	    } elsif ($_ =~ m;^[[:space:]]*reads/s:[[:space:]]*([[:digit:].]+);) {
		$readops = $1;
	    } elsif ($_ =~ m;^[[:space:]]*writes/s:[[:space:]]*([[:digit:].]+);) {
		$writeops = $1;
	    } elsif ($_ =~ m;^[[:space:]]*fsyncs/s:[[:space:]]*([[:digit:].]+);) {
		$fsyncops = $1;
	    } elsif ($_ =~ m;^[[:space:]]*read, MiB/s:[[:space:]]*([[:digit:].]+);) {
		$readrate = $1;
	    } elsif ($_ =~ m;^[[:space:]]*written, MiB/s:[[:space:]]*([[:digit:].]+);) {
		$writerate = $1;
	    } elsif ($_ =~ m;^[[:space:]]*total time:[[:space:]]*([[:digit:].]+)s;) {
		$et = $1;
	    } elsif ($_ =~ m;^[[:space:]]*min:[[:space:]]*([[:digit:].]+);) {
		$min_lat = $1 / 1000.0;
	    } elsif ($_ =~ m;^[[:space:]]*avg:[[:space:]]*([[:digit:].]+);) {
		$avg_lat = $1 / 1000.0;
	    } elsif ($_ =~ m;^[[:space:]]*max:[[:space:]]*([[:digit:].]+);) {
		$max_lat = $1 / 1000.0;
	    } elsif ($_ =~ m;^[[:space:]]*95th percentile:[[:space:]]*([[:digit:].]+);) {
		$p95_lat = $1 / 1000.0;
	    }
	    if ($ENV{"VERBOSE"} > 0) {
		chomp;
		timestamp($_);
	    }
	}
	close RUN;
	my ($op1_user, $op1_sys) = cputime();
	do_sync($synchost, $syncport);
	timestamp("Cleanup...");
	timestamp("sysbench --time=$runtime $sysbench_generic_args $sysbench_cmd cleanup --file-test-mode=$mode $sysbench_fileio_args");
	open(CLEANUP, "-|", "sysbench --time=$runtime $sysbench_generic_args $sysbench_cmd cleanup --file-test-mode=$mode $sysbench_fileio_args") || die "Can't run sysbench: $!\n";
	while (<CLEANUP>) {
	    if ($ENV{"VERBOSE"} > 0) {
		chomp;
		timestamp($_);
	    }
	}
	close CLEANUP;
	my ($op_answer) = sprintf($op_answer_fstring, $mode, $readops, $writeops, $fsyncops, $readrate,
				     $writerate, $et, $min_lat, $avg_lat, $max_lat, $p95_lat,
				     $files, $filesize, $blocksize, $rdwr_ratio, $fsync_frequency,
				     $final_fsync_enabled, $io_mode, $op1_user - $op0_user,
				     $op1_sys - $op0_sys);
	push @op_answers, $op_answer;
    }
    my $data_end_time = xtime();
    my ($elapsed_time) = $data_end_time - $data_start_time;
    my ($base1_user, $base1_sys) = cputime();
    my ($user) = $base1_user - $base0_user;
    my ($sys) = $base1_sys - $base0_sys;
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
  "workloads": {%s}
}
EOF
    my ($answer) = sprintf($fstring, $namespace, $pod, $container, $$, $crtime - $basetime,
			   $start_time - $basetime, $data_start_time - $basetime,
			   $data_end_time - $basetime, $elapsed_time, $user, $sys,
			   join(",", @op_answers));
    print STDERR "$answer\n";
    do_sync($synchost, $syncport, $answer);
    if ($logport > 0) {
	do_sync($loghost, $logport, $answer);
    }
}
$SIG{CHLD} = 'IGNORE';
if ($processes > 1) {
    for (my $i = 0; $i < $processes; $i++) {
        if ((my $child = fork()) == 0) {
            runit();
            exit(0);
        }
    }
} else {
    runit();
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
