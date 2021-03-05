#!/usr/bin/perl

use Socket;
use POSIX;
use strict;
use Time::Piece;
use Time::HiRes qw(gettimeofday);
our ($namespace, $pod, $container, $basetime, $baseoffset, $crtime, $poddelay, $processes, $runtime, $exit_at_end, $synchost, $syncport, $loghost, $logport) = @ARGV;
$SIG{TERM} = sub { kill 'KILL', -1; POSIX::_exit(0); };
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
my ($dstime) = xtime();
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
    my ($iterations) = 0;
    my ($loops_per_iteration) = 10000;
    my ($basecpu) = cputime();
    my ($prevcpu) = $basecpu;
    my ($firsttime) = 1;
    my ($avgcpu) = 0;
    my ($weight) = .25;
    my ($icputime);
    my ($interval) = 5;
    my $start_time;

    my $delaytime = $basetime + $poddelay - $dstime;
    do_sync($synchost, $syncport);
    my ($stime1) = xtime();
    my ($stime) = $stime1;
    my ($prevtime) = $stime;
    my ($scputime) = cputime();
    while ($runtime < 0 || xtime() - $stime1 < $runtime) {
        my ($a) = 1;
        for (my $i = 0; $i < $loops_per_iteration; $i++) {
            $a = $a + $a;
        }
        $iterations += $loops_per_iteration;
        if ($ENV{"VERBOSE"} > 0) {
	    my ($ntime) = xtime();
	    if ($ntime - $prevtime >= $interval) {
		my (@times) = times();
		my ($user, $system, $cuser, $csystem) = times();
		my ($etime) = $ntime - $stime;
		my ($cpu) = cputime();
		my ($cputime) = $cpu - $basecpu;
		my ($icputime) = $cpu - $prevcpu;
		if ($firsttime) {
		    $avgcpu = $cputime;
		    $firsttime = 0;
		} else {
		    $avgcpu = ($icputime * $weight) + ($avgcpu * (1.0 - $weight));
		}
		printf STDERR "pid %d elapsed %.03f cpu %0.3f util %7.3f avg %7.3f mov %7.3f iter %d ips %d\n", $$, $etime, $cputime, 100.0 * $cputime / $etime, 100.0 * $icputime / ($ntime - $prevtime), 100 * $avgcpu / ($ntime - $prevtime), $iterations, $iterations / $etime;
		$prevtime = $ntime;
		$prevcpu = $cpu;
            }
        }
    }
    my ($etime) = xtime();
    my ($eltime) = $etime - $stime1;
    my ($cputime) = cputime() - $scputime;
    my ($answer) = sprintf("STATS %d %.3f %.3f %.3f %.3f %.3f %.3f %7.3f %d %d",
        $$, $crtime - $basetime, $dstime - $basetime, $stime1 - $basetime,
        $eltime, $etime - $basetime, $cputime, 100.0 * $cputime / $eltime, $iterations,
        $iterations / ($etime - $stime1));
    print STDERR "$answer\n";
    do_sync($synchost, $syncport, $answer);
    do_sync($loghost, $logport, "-n $namespace $pod -c $container terminated 0 0 0 $answer");
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
print STDERR "FINIS\n";
if ($exit_at_end) {
    timestamp("About to exit");
    while (wait() > 0) {}
    timestamp("Done waiting");
    POSIX::_exit(0);
} else {
    timestamp("Waiting forever");
    pause()
}
