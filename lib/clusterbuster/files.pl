#!/usr/bin/perl

use Socket;
use POSIX;
use strict;
use Time::Piece;
use Time::HiRes qw(gettimeofday);
#use File::Sync qw(sync);
our ($namespace, $pod, $container, $basetime, $baseoffset, $crtime, $poddelay, $exit_delay, $synchost, $syncport, $dirs, $files_per_dir, $blocksize, $block_count, $processes, $loghost, $logport, @dirs) = @ARGV;
$SIG{TERM} = sub { POSIX::_exit(0); };
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


sub runit($) {
    my ($process) = @_;
    my ($basecpu) = cputime();
    my ($prevcpu) = $basecpu;
    my ($iterations) = 1;

    my $delaytime = $basetime + $poddelay - $dstime;
    do_sync($synchost, $syncport);
    my ($stime1) = xtime();
    my ($stime) = $stime1;
    my ($prevtime) = $stime;
    my ($scputime) = cputime();
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
    sleep($exit_delay);
    foreach my $bdir (@dirs) {
	my ($pdir)="$bdir/p$process";
	my ($dir)="$pdir/$container";
	foreach my $subdir (0..$dirs-1) {
	    my ($dirname) = "$dir/d$subdir";
	    foreach my $file (0..$files_per_dir-1) {
		my ($filename) = "$dirname/f$file";
		unlink($filename) || die "Can't remove $filename: $!\n";
		$ops++;
	    }
	    rmdir("$dirname") || die("Can't remove directory $dirname: $!\n");
	    $ops++;
	}
	rmdir("$dir") || die("Can't remove directory $dir: $!\n");
	$ops++;
	rmdir("$pdir") || die("Can't create directory $pdir: $!\n");
	$ops++;
    }
    system("sync");
#    sync();
    my ($etime) = xtime();
    my ($eltime) = $etime - $stime1;
    my ($cputime) = cputime() - $scputime;
    my ($answer) = sprintf("STATS %d %.3f %.3f %.3f %.3f %.3f %.3f %7.3f %d %d %d",
        $$, $crtime - $basetime, $dstime - $basetime, $stime1 - $basetime,
        $eltime, $etime - $basetime, $cputime, 100.0 * $cputime / $eltime, $ops, $iterations,
        $iterations / ($etime - $stime1));
    print STDERR "$answer\n";
    do_sync($synchost, $syncport, $answer);
    do_sync($loghost, $logport, "-n $namespace $pod -c $container terminated 0 0 0 $answer");
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
timestamp("About to exit");
while (wait() > 0) {}
timestamp("Done waiting");
POSIX::_exit(0);
