#!/usr/bin/perl

use Socket;
use POSIX;
use strict;
use Time::HiRes qw(gettimeofday usleep);
use Time::Piece;
$SIG{TERM} = sub { kill 'KILL', -1; POSIX::_exit(0); };
my ($namespace, $pod, $container, $basetime, $baseoffset, $poddelay, $connect_port, $container, $srvhost, $data_rate, $bytes, $bytesMax, $msgSize, $xfertime, $xfertimeMax, $crtime, $exit_at_end, $synchost, $syncport, $namespace, $loghost, $logport, $podname) = @ARGV;
$basetime += $baseoffset;
$crtime += $baseoffset;
my ($etime, $data_sent, $detime, $stime, $end_time, $dstime, $mean, $max, $stdev, $user, $sys, $cuser, $csys, $elapsed);
my $start_time;
my $ghbn_time;
my $pass = 0;
my $ex = 0;
my $ex2 = 0;
my ($cfail) = 0;
my ($refused) = 0;
my $time_overhead = 0;
sub ts() {
    my (@now) = gettimeofday();
    return sprintf("%s.%06d", gmtime($now[0])->strftime("%Y-%m-%dT%T"), $now[1]);
}
sub timestamp($) {
    my ($str) = @_;
    printf STDERR "%s %s %s\n", $container, ts(), $str;
}
sub xtime() {
    my (@now) = gettimeofday();
    return $now[0] + ($now[1] / 1000000.0);
}
sub calibrate_time() {
    for (my $i = 0; $i < 1000; $i++) {
        my ($start) = xtime();
	my ($end) = xtime();
	$time_overhead += $end - $start;
    }
    $time_overhead /= 1000;
}
sub stats() {
    return
	sprintf("-n,%s,%s,-c,%s,terminated,%d,%d,%d,STATS,%.3f,%.3f,%.3f,%.3f,%.3f,%.3f,%.6f,%.3f,%.3f,%d,%.3f,%.3f,%.6f,%.6f,%.6f,%.6f,%d",
		$namespace, $pod, $container, $cfail, $refused, $pass,
		$crtime - $basetime, $start_time - $basetime, $ghbn_time - $basetime, $etime - $basetime,
		$dstime - $basetime, $end_time - $basetime, $elapsed, $user, $sys,
		$data_sent, $detime, $data_sent / $detime / 1000000.0, $mean, $max, $stdev, $time_overhead, $pass);
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
	    $cfail++;
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
	        $cfail++;
		if ($! =~ /refused/) {
		    $refused++;
		}
                timestamp("Could not connect to $addr on port $port: $!");
                close $sock;
                sleep(1);
            }
        }
    } while (! $connected);
    return ($sock, $ghbn_time, $stime);
}
$SIG{TERM} = sub { POSIX::_exit(0); };
timestamp("Clusterbuster client starting");
$start_time = xtime();
my ($conn);
($conn, $ghbn_time, $stime) = connect_to($srvhost, $connect_port);
$SIG{TERM} = sub { close $conn; POSIX::_exit(0); };

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
	my ($_conn, $i1, $i2) = connect_to($addr, $port);
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
do_sync($synchost, $syncport);
$etime = xtime();
$elapsed = $etime - $stime;
my $peeraddr = getpeername($conn);
my ($port, $addr) = sockaddr_in($peeraddr);
my $peerhost = gethostbyaddr($addr, AF_INET);
$peeraddr = inet_ntoa($addr);
timestamp("Connected to $peerhost ($peeraddr) on port tcp:$port");
my $buffer = "";
vec($buffer, $msgSize - 1, 8) = "A";
my $nread;
my $bufsize = length($buffer);
my $starttime = xtime();
my $MBSec = $data_rate * 1;
($dstime) = xtime();

$data_sent = 0;
$mean = 0;
$max = 0;
$stdev = 0;
if ($bytes != $bytesMax) {
    $bytes += int(rand($bytesMax - $bytes + 1));
}
if ($xfertime != $xfertimeMax) {
    $xfertime += int(rand($xfertimeMax - $xfertime + 1));
}
if ($MBSec != 0) {
    calibrate_time();
    my $delaytime = $basetime + $poddelay - $dstime;
    timestamp("Using $bufsize byte buffer");
    if ($delaytime > 0) {
	timestamp("Sleeping $delaytime seconds to synchronize");
	usleep($delaytime * 1000000);
    }
    $dstime = xtime();
    my ($tbuf, $rtt_start, $rtt_elapsed, $en);
    while (($bytes > 0 && $data_sent < $bytes) ||
	   ($xfertime > 0 && xtime() - $dstime < $xfertime)) {
	my $nwrite;
	my $nleft = $bufsize;
	$rtt_start = xtime();
	while ($nleft > 0 && ($nwrite = syswrite($conn, $buffer, $nleft)) > 0) {
	    $nleft -= $nwrite;
	    $data_sent += $nwrite;
	}
	if ($nwrite == 0) {
	    exit 0;
	} elsif ($nwrite < 0) {
	    die "Write failed: $!\n";
	}
	$nleft = $bufsize;
	while ($nleft > 0 && ($nread = sysread($conn, $tbuf, $nleft)) > 0) {
	    $nleft -= $nread;
	}
	$en = xtime() - $rtt_start - $time_overhead;
	$ex += $en;
	$ex2 += $en * $en;
	if ($en > $max) {
	    $max = $en;
	}
	if ($nread < 0) {
	    die "Read failed: $!\n";
	}
	if ($ENV{"VERBOSE"} > 0) {
	    timestamp(sprintf("Write/Read %d %.6f", $bufsize, $en));
	}
	my $curtime = xtime();
	$starttime += $bufsize / ($MBSec * 1000000);
	if ($curtime < $starttime && $MBSec > 0) {
	    if ($ENV{"VERBOSE"} > 0) {
		timestamp(sprintf("Sleeping %8.6f", $starttime - $curtime));
	    }
	    usleep(($starttime - $curtime) * 1000000);
	} else {
	    if ($ENV{"VERBOSE"} > 0 && $MBSec > 0) {
		timestamp("Not sleeping");
	    }
	}
	$pass++;
    }
}
if ($pass > 0) {
    $mean = ($ex / $pass);
    if ($pass > 1) {
	$stdev = sqrt(($ex2 - ($ex * $ex / $pass)) / ($pass - 1));
    }
}
($user, $sys, $cuser, $csys) = times;
$end_time = xtime();
$detime = $end_time - $dstime;
if ($detime <= 0) {
    $detime = 0.00000001;
}

timestamp("Done");
my ($results) = stats();
print STDERR "$results\n";
print STDERR "FINIS\n";
if ($syncport) {
    do_sync($synchost, $syncport, $results);
}
if ($logport > 0) {
    do_sync($loghost, $logport, $results);
}
if (! $exit_at_end) {
    pause();
}
exit 0;
