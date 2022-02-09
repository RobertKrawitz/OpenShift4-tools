#!/usr/bin/perl

use Socket;
use POSIX;
use strict;
use Time::Piece;
use Time::HiRes qw(gettimeofday);
use Sys::Hostname;
our ($namespace, $container, $basetime, $baseoffset, $poddelay, $crtime, $exit_at_end, $synchost, $syncport, $loghost, $logport, $processes, $runtime) = @ARGV;
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
my ($start_time) = xtime();
my ($pod) = hostname;
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

sub runit() {
    my ($iterations) = 0;
    my ($loops_per_iteration) = 10000;
    my ($firsttime) = 1;
    my ($avgcpu) = 0;
    my ($weight) = .25;
    my ($icputime);
    my ($interval) = 5;

    my $delaytime = $basetime + $poddelay - $start_time;
    if ($delaytime > 0) {
	timestamp("Sleeping $delaytime seconds to synchronize");
	usleep($delaytime * 1000000);
    }
    do_sync($synchost, $syncport);
    my ($data_start_time) = xtime();
    my ($suser, $ssys, $scuser, $scsys) = times;
    my ($scputime) = cputime();
    my ($basecpu) = $scputime;
    my ($prevcpu) = $basecpu;
    my ($prevtime) = $start_time;
    while ($runtime < 0 || xtime() - $start_time < $runtime) {
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
		my ($etime) = $ntime - $start_time;
		my ($cpu) = cputime();
		my ($cputime) = $cpu - $basecpu;
		my ($icputime) = $cpu - $prevcpu;
		if ($firsttime) {
		    $avgcpu = $cputime;
		    $firsttime = 0;
		} else {
		    $avgcpu = ($icputime * $weight) + ($avgcpu * (1.0 - $weight));
		}
		$prevtime = $ntime;
		$prevcpu = $cpu;
            }
        }
    }
    my ($data_end_time) = xtime();
    my ($cputime) = cputime() - $scputime;
    my ($euser, $esys, $ecuser, $ecsys) = times;
    my ($user) = $euser - $suser;
    my ($sys) = $esys - $ssys;
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
  "work_iterations": %d
}
EOF
    $fstring =~ s/[ \n]+//g;
    my ($elapsed_time) = $data_end_time - $data_start_time;
    my ($answer) = sprintf($fstring, $namespace, $pod, $container, $$, $crtime - $basetime,
			   $start_time - $basetime, $data_start_time - $basetime,
			   $data_end_time - $basetime, $elapsed_time, $user, $sys,
			   $iterations);
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
