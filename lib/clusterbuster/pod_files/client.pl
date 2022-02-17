#!/usr/bin/perl

use Socket;
use POSIX;
use strict;
use Time::HiRes qw(gettimeofday usleep);
use Time::Piece;
use Sys::Hostname;
use File::Basename;
my ($dir) = $ENV{'BAK_CONFIGMAP'};
require "$dir/clientlib.pl";

my ($namespace, $container, $basetime, $baseoffset, $poddelay, $crtime, $exit_at_end, $synchost, $syncport, $loghost, $logport, $srvhost, $connect_port, $data_rate, $bytes, $bytes_max, $msg_size, $xfertime, $xfertime_max) = @ARGV;
my ($start_time, $data_start_time, $data_end_time, $elapsed_time, $end_time, $user, $sys, $cuser, $csys);

$SIG{TERM} = sub { POSIX::_exit(0); };
$basetime += $baseoffset;
$crtime += $baseoffset;

my ($data_sent);
my ($mean_latency, $max_latency, $stdev_latency);

$start_time = xtime();
my $pass = 0;
my $ex = 0;
my $ex2 = 0;
my ($cfail) = 0;
my ($refused) = 0;
my $time_overhead = 0;
my ($pod) = hostname;

sub stats() {
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
  "data_sent_bytes": %d,
  "mean_latency_sec": %f,
  "max_latency_sec": %f,
  "stdev_latency_sec": %f,
  "timing_overhead_sec": %f,
  "target_data_rate": %f,
  "passes": %d,
  "msg_size": %d
}
EOF
    $fstring =~ s/[ \n]+//g;
    return sprintf($fstring, $namespace, $pod, $container, $$, $crtime - $basetime,
		   $start_time - $basetime, $data_start_time - $basetime,
		   $data_end_time - $basetime, $elapsed_time, $user, $sys, $user + $sys,
		   $data_sent, $mean_latency, $max_latency, $stdev_latency, $time_overhead,
		   $data_rate, $pass, $msg_size);
}

$SIG{TERM} = sub { POSIX::_exit(0); };
timestamp("Clusterbuster client starting");
my ($conn) = connect_to($srvhost, $connect_port);
$SIG{TERM} = sub { close $conn; POSIX::_exit(0); };

do_sync($synchost, $syncport);
my $peeraddr = getpeername($conn);
my ($port, $addr) = sockaddr_in($peeraddr);
my $peerhost = gethostbyaddr($addr, AF_INET);
$peeraddr = inet_ntoa($addr);
timestamp("Connected to $peerhost ($peeraddr) on port tcp:$port");
my $buffer = "";
vec($buffer, $msg_size - 1, 8) = "A";
my $nread;
my $bufsize = length($buffer);
$data_rate = $data_rate * 1;

$data_sent = 0;
$mean_latency = 0;
$max_latency = 0;
$stdev_latency = 0;
if ($bytes != $bytes_max) {
    $bytes += int(rand($bytes_max - $bytes + 1));
}
if ($xfertime != $xfertime_max) {
    $xfertime += int(rand($xfertime_max - $xfertime + 1));
}
calibrate_time();
timestamp("Using $bufsize byte buffer");
my ($start_time) = xtime();
my ($starttime) = $data_start_time;
my $delaytime = $basetime + $poddelay - $start_time;
if ($delaytime > 0) {
    timestamp("Sleeping $delaytime seconds to synchronize");
    usleep($delaytime * 1000000);
}
$data_start_time = xtime();
my ($tbuf, $rtt_start, $rtt_elapsed, $en);
while (($bytes > 0 && $data_sent < $bytes) ||
       ($xfertime > 0 && xtime() - $data_start_time < $xfertime)) {
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
    if ($en > $max_latency) {
	$max_latency = $en;
    }
    if ($nread < 0) {
	die "Read failed: $!\n";
    }
    if ($ENV{"VERBOSE"} > 0) {
	timestamp(sprintf("Write/Read %d %.6f", $bufsize, $en));
    }
    my $curtime = xtime();
    if ($data_rate > 0) {
	$starttime += $bufsize / $data_rate;
	if ($curtime < $starttime) {
	    if ($ENV{"VERBOSE"} > 0) {
		timestamp(sprintf("Sleeping %8.6f", $starttime - $curtime));
	    }
	    usleep(($starttime - $curtime) * 1000000);
	} else {
	    if ($ENV{"VERBOSE"} > 0) {
		timestamp("Not sleeping");
	    }
	}
    }
    $pass++;
}
$data_end_time = xtime();
if ($pass > 0) {
    $mean_latency = ($ex / $pass);
    if ($pass > 1) {
	$stdev_latency = sqrt(($ex2 - ($ex * $ex / $pass)) / ($pass - 1));
    }
}
($user, $sys, $cuser, $csys) = times;
$elapsed_time = $data_end_time - $data_start_time;
if ($elapsed_time <= 0) {
    $elapsed_time = 0.00000001;
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
