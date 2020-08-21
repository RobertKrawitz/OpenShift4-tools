#!/usr/bin/perl

use Socket;
use POSIX;
use strict;
use Time::Piece;
use Time::HiRes qw(gettimeofday);
our ($namespace, $pod, $container, $basetime, $baseoffset, $crtime, $poddelay, $exit_delay, $synchost, $syncport, $dirs, $files_per_dir, $blocksize, $block_count, @dirs) = @ARGV;

$basetime += $baseoffset;
$crtime += $baseoffset;
my ($time_overhead) = 0;
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
$SIG{TERM} = sub { POSIX::_exit(0); };

timestamp("Filebuster client starting");

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

if ($#dirs < 0) {
    @dirs=("/tmp");
}

my ($buffer);
vec($buffer, $blocksize - 1, 8) = "A";

foreach my $dir (@dirs) {
    foreach my $subdir (0..$dirs-1) {
	my ($dirname) = "$dir/d$subdir";
	mkdir("$dirname") || die("Can't create directory $dirname: $!\n");
	foreach my $file (0..$files_per_dir-1) {
	    my ($filename) = "$dirname/f$file";
	    open(FILE, ">", $filename) || die "Can't create file $filename: $!\n";
	    foreach my $block (0..$block_count - 1) {
		if (syswrite(FILE, $buffer, $blocksize) != $blocksize) {
		    die "Write to $filename failed: $!\n";
		}
	    }
	}
    }
}

sleep($exit_delay);
