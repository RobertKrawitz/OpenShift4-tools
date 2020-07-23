#!/usr/bin/perl

use Socket;
use POSIX;
use strict;
use Time::Piece;
use Time::HiRes qw(gettimeofday);
our ($namespace, $pod, $container, $basetime, $baseoffset, $crtime, $poddelay, $processes, $rundir, $runtime, $exit_at_end, $synchost, $syncport, $loghost, $logport, $jobfiles_dir, $fio_generic_args) = @ARGV;
$SIG{TERM} = sub { kill 'KILL', -1; POSIX::_exit(0); };
$basetime += $baseoffset;
$crtime += $baseoffset;
$rundir .= "/$$";
if (! mkdir($rundir)) {
    timestamp("Cannot create run directory $rundir: $!");
    exit(1);
}
if (! chdir($rundir)) {
    timestamp("Cannot cd $rundir: $!");
    exit(1);
}

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

sub runit(;$) {
    my ($jobfile) = @_;
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
    timestamp("fio $fio_generic_args --output-format=json+ $jobfile");
    pipe(READER, WRITER) || die "Can't create pipe: $!\n";
    my ($pid) = fork();
    if ($pid == -1) {
        die "Can't fork: $!\n";
    } elsif ($pid == 0) {
        close READER;
	open(STDOUT, ">&WRITER") || die "Can't dup stdout to writer: $!\n";
	open(STDERR, ">&WRITER") || die "Can't dup stderr to writer: $!\n";
	exec("/bin/bash", "-c", "fio $fio_generic_args --output-format=json+ $jobfile") || die "Can't run fio: $!\n";
        # NOTREACHED
	exit(1);
    } else {
        close WRITER;
	while (<READER>) {
	    print STDERR $_;
	}
	close WRITER;
    }
    my ($child) = wait();
    if ($child < 0) {
        print STDERR "*** Can't reap child (expected $pid, got $child)!\n";
    } else {
        my ($status) = $? >> 8;
        print STDERR "fio returned $status\n";
    }
#    my ($answer) = sprintf("STATS %d %.3f %.3f %.3f %d %d %d %d %d %.03f %.06f %.06f %.06f %.06f",
#	    $$, $crtime - $basetime, $dstime - $basetime, $stime1 - $basetime,
#	    $readops, $writeops, $fsyncops, $readrate, $writerate, $et, $min_lat, $avg_lat, $max_lat, $p95_lat);
#    print STDERR "$answer\n";
#    do_sync($synchost, $syncport, $answer);
     do_sync($synchost, $syncport);
#    do_sync($loghost, $logport, "-n $namespace $pod -c $container terminated 0 0 0 $answer");
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
