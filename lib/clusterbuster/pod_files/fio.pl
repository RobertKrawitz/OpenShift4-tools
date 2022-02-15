#!/usr/bin/perl

use Socket;
use POSIX;
use strict;
use Time::Piece;
use Time::HiRes qw(gettimeofday usleep);
use File::Path qw(make_path remove_tree);
use Sys::Hostname;
our ($namespace, $container, $basetime, $baseoffset, $poddelay, $crtime, $exit_at_end, $synchost, $syncport, $loghost, $logport, $processes, $rundir, $runtime, $jobfiles_dir, $fio_generic_args) = @ARGV;

my ($data_start_time, $data_end_time);
$SIG{TERM} = sub() { docleanup() };
$basetime += $baseoffset;
$crtime += $baseoffset;
my ($start_time) = xtime();

my ($pod) = hostname;
my ($localrundir) = "$rundir/$pod/$$";

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
    removeRundir();
    kill 'KILL', -1;
    POSIX::_exit(0);
}

removeRundir();

if (! make_path($localrundir)) {
    timestamp("Cannot create run directory $localrundir: $!");
}
if (! chdir($localrundir)) {
    timestamp("Cannot cd $localrundir: $!");
    exit(1);
}

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

sub runit(;$) {
    my ($jobfile) = @_;
    my ($firsttime) = 1;
    my ($avgcpu) = 0;
    my ($weight) = .25;
    my ($icputime);
    my ($interval) = 5;
    my ($dstime) = xtime();

    my $delaytime = $basetime + $poddelay - $dstime;
    if ($delaytime > 0) {
	timestamp("Sleeping $delaytime seconds to synchronize");
	usleep($delaytime * 1000000);
    }
    do_sync($synchost, $syncport);
    my ($ucpu0, $scpu0) = cputime();
    my ($answer0) = '';
    timestamp("Running...");
    my ($data_start_time) = xtime();
    timestamp("fio $fio_generic_args --output-format=json+ $jobfile");
    open(RUN, "-|", "fio $fio_generic_args --output-format=json+ $jobfile | jq -c .") || die "Can't run fio: $!\n";
    while (<RUN>) {
	$answer0 .= "$_";
    }
    close(RUN);
    my ($data_end_time) = xtime();
    my ($ucpu1, $scpu1) = cputime();
    $ucpu1 -= $ucpu0;
    $scpu1 -= $scpu0;
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
  "results": %s
}
EOF
    $fstring =~ s/[ \n]+//g;
    my ($answer) = sprintf($fstring, $namespace, $pod, $container, $$, $crtime - $basetime,
			   $start_time - $basetime, $data_start_time - $basetime,
			   $data_end_time - $basetime, $data_end_time - $data_start_time,
			   $ucpu1, $scpu1, $ucpu1 + $scpu1,
			   $answer0 eq '' ? '{}' : $answer0);

    do_sync($synchost, $syncport, $answer);
    if ($logport > 0) {
	do_sync($loghost, $logport, $answer);
    }
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
	    docleanup();
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
