#!/usr/bin/perl

use Socket;
use POSIX;
use strict;
use Time::Piece;
use Time::HiRes qw(gettimeofday);
use Sys::Hostname;
#use File::Sync qw(sync);
our ($namespace, $container, $basetime, $baseoffset, $crtime, $poddelay, $exit_delay, $synchost, $syncport, $dirs, $files_per_dir, $blocksize, $block_count, $processes, $loghost, $logport, @dirs) = @ARGV;
$SIG{TERM} = sub { POSIX::_exit(0); };
$basetime += $baseoffset;
$crtime += $baseoffset;
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

if ($#dirs < 0) {
    @dirs=("/tmp");
}
my ($buffer);
vec($buffer, $blocksize - 1, 8) = "A";

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

sub runit($) {
    my ($process) = @_;
    my ($basecpu) = cputime();
    my ($prevcpu) = $basecpu;
    my ($iterations) = 1;

    my $delaytime = $basetime + $poddelay - $dstime;
    # Make sure everything is cleared out first...but don't count the time here.
    removethem($process, 1);

    do_sync($synchost, $syncport);
    my ($stime1) = xtime();
    my ($stime0) = $stime1;
    my ($stime) = $stime1;
    my ($prevtime) = $stime;
    my ($ucpu0, $scpu0) = cputime();
    timestamp("Creating files...");
    my ($ops) = makethem($process);
    system("sync");
    my ($etime) = xtime();
    my ($eltime) = $etime - $stime1;
    my ($ucpu1, $scpu1) = cputime();
    $ucpu1 -= $ucpu0;
    $scpu1 -= $scpu0;
    my ($fstring0) = <<'EOF';
"%s": {
  "elapsed_time": %f,
  "user_cpu_time": %f,
  "system_cpu_time": %f,
  "cpu_utilization": %f,
  "operations": %d,
  "iterations": %d,
  "iterations_per_second": %f
}
EOF
    $fstring0 =~ s/[ \n]+//g;
    my ($answer0) = sprintf($fstring0, "create",
        $eltime, $ucpu1,
	$scpu1, ($ucpu1 + $scpu1) / $eltime, $ops, $iterations,
        $iterations / ($etime - $stime1));
    timestamp("Created files...");
    do_sync($synchost, $syncport);

    timestamp("Sleeping for $exit_delay");
    sleep($exit_delay);
    timestamp("Back from sleep");
    $ops = 0;

    do_sync($synchost, $syncport);
    my ($stime1) = xtime();
    my ($stime) = $stime1;
    my ($prevtime) = $stime;
    my ($ucpu0, $scpu0) = cputime();
    timestamp("Removing files...");
    my ($ops) = removethem($process);
    timestamp("Removed files...");
    system("sync");
    my ($etime) = xtime();
    my ($eltime) = $etime - $stime1;
    my ($ucpu1, $scpu1) = cputime();
    $ucpu1 -= $ucpu0;
    $scpu1 -= $scpu0;
    my ($answer1) = sprintf($fstring0, "remove",
        $eltime, $ucpu1,
	$scpu1, ($ucpu1 + $scpu1) / $eltime, $ops, $iterations,
        $iterations / ($etime - $stime1));
    my ($fstring) = <<'EOF';
{
  "application": "clusterbuster-json",
  "namespace": "%s",
  "pod": "%s",
  "container": "%s",
  "connections_failed": %d,
  "connections_refused": %d,
  "connections_succeeded": %d,
  "start_time_offset_from_base": %f,
  "elapsed_time_seconds": %f,
  "block_count": %d,
  "block_size": %d,
%s,
%s
}
EOF
    $fstring =~ s/[ \n]+//g;
    my ($answer) = sprintf($fstring, $namespace, $pod, $container, 0, 0, 0,
			   $stime0 - $basetime, $etime - $stime0,
			   $block_count, $blocksize,
			   $answer0, $answer1);
    print STDERR "$answer\n";
    do_sync($synchost, $syncport, "$answer");
    if ($logport > 0) {
	do_sync($loghost, $logport, "$answer");
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
