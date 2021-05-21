#!/usr/bin/perl

use Socket;
use POSIX;
use strict;
use Time::Piece;
use Time::HiRes qw(gettimeofday);
use File::Path qw(make_path remove_tree);
use Sys::Hostname;
our ($namespace, $pod, $container, $basetime, $baseoffset, $crtime, $poddelay, $processes, $rundir, $runtime, $exit_at_end, $synchost, $syncport, $loghost, $logport, $sysbench_generic_args, $sysbench_cmd, $sysbench_fileio_args, $sysbench_modes) = @ARGV;
my ($local_hostname) = hostname;
my ($localrundir) = "$rundir/$local_hostname/$$";

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
print STDERR "HERE!\n";
$basetime += $baseoffset;
$crtime += $baseoffset;

sub cputime() {
    my (@times) = times();
    return $times[0] + $times[1] + $times[2] + $times[3];
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
    if (not $token) {
        $token = sprintf('%d', rand() * 999999999);
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

sub runit() {
    my ($files) = 0;
    my ($totalbytes) = 0;
    my ($seconds) = 0;
    my ($rate) = 0;
    my ($readops) = 0;
    my ($writeops) = 0;
    my ($fsyncops) = 0;
    my ($readrate) = 0;
    my ($writerate) = 0;
    my ($et) = 0;
    my ($min_lat) = 0;
    my ($avg_lat) = 0;
    my ($max_lat) = 0;
    my ($p95_lat) = 0;
    my (@known_sysbench_fileio_modes) = qw(seqwr seqrewr seqrd rndrd rndwr rndrw);
    my ($iterations) = 0;
    my ($loops_per_iteration) = 10000;
    if ($sysbench_modes) {
        @known_sysbench_fileio_modes = split(/ +/, $sysbench_modes);
    }
    timestamp(join("|", @known_sysbench_fileio_modes));
    my ($mode) = $known_sysbench_fileio_modes[int(rand() * ($#known_sysbench_fileio_modes + 1.0))];
    removeRundir();
    if (! make_path($localrundir)) {
        timestamp("Cannot create run directory $localrundir: $!");
	exit(1);
    }
    if (! chdir($localrundir)) {
        timestamp("Cannot cd $localrundir: $!");
	exit(1);
    }
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

    my ($basecpu) = cputime();
    my ($prevcpu) = $basecpu;
    my ($firsttime) = 1;
    my ($avgcpu) = 0;
    my ($weight) = .25;
    my ($icputime);
    my ($interval) = 5;
    my $start_time;
    my ($dstime) = xtime();

    my $delaytime = $basetime + $poddelay - $dstime;
    do_sync($synchost, $syncport);
    my ($stime1) = xtime();
    my ($stime) = $stime1;
    my ($prevtime) = $stime;
    my ($scputime) = cputime();
    timestamp("Running...");
    timestamp("sysbench --time=$runtime $sysbench_generic_args $sysbench_cmd run --file-test-mode=$mode $sysbench_fileio_args");
    open(RUN, "-|", "sysbench --time=$runtime $sysbench_generic_args $sysbench_cmd run --file-test-mode=$mode $sysbench_fileio_args") || die "Can't run sysbench: $!\n";
    while (<RUN>) {
	if ($_ =~ m;^[[:space:]]*reads/s:[[:space:]]*([[:digit:].]+);) {
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
    my ($answer) = sprintf("-n,%s,%s,-c,%s,terminated,%d,%d,%d,STATS %d %.3f %.3f %.3f %d %d %d %d %d %.03f %.06f %.06f %.06f %.06f",
			   $namespace, $pod, $container, 0, 0, 0,
	    $$, $crtime - $basetime, $dstime - $basetime, $stime1 - $basetime,
	    $readops, $writeops, $fsyncops, $readrate, $writerate, $et, $min_lat, $avg_lat, $max_lat, $p95_lat);
    print STDERR "$answer\n";
    docleanup();
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
