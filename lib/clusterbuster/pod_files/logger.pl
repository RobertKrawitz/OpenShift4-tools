#!/usr/bin/perl

use Socket;
use POSIX;
use strict;
use Time::Piece;
use Time::HiRes qw(gettimeofday usleep);
use Sys::Hostname;
use File::Basename;
my ($dir) = $ENV{'BAK_CONFIGMAP'};
require "$dir/clientlib.pl";

$SIG{TERM} = sub { POSIX::_exit(0); };
our ($namespace, $container, $bytes_per_line, $bytes_per_io, $xfer_count, $processes, $delay_usecs, $xfer_time, $exit_at_end) = @ARGV;

timestamp("Clusterbuster logger starting");
my ($pod) = hostname;

while ($processes-- > 0) {
    if ((my $child = fork()) == 0) {
	my $linebuf = "";
	for (my $i = 0; $i < $bytes_per_line; $i++) {
	    $linebuf .= 'A';
	}
	$linebuf .= "\n";
	my ($buffer);
	my ($bufsize) = 0;
	do {
	    $buffer .= $linebuf;
	    $bufsize += length $linebuf;
	} while ($bufsize < $bytes_per_io);
	my ($start_time) = xtime();
	my ($xfers) = 0;
	while (($xfer_time == 0 && $xfer_count == 0) ||
	       ($xfer_time > 0 && xtime() - ($start_time + $xfer_time) < 0) ||
	       ($xfer_count > 0 && $xfers++ < $xfer_count)) {
	    my ($bytes_left) = $bufsize;
	    while ($bytes_left > 0) {
		my ($answer) = syswrite(STDERR, $buffer, $bytes_left);
		if ($answer > 0) {
		    $bytes_left -= $answer;
		} else {
		    exit(1);
		}
	    }
	    if ($delay_usecs > 0) {
		usleep($delay_usecs);
	    }
	}
	if (! $exit_at_end) {
	    sleep;
	}
	exit(0);
    }
}

while ((my $child = wait()) >= 0) {
    if ($? > 0) {
	timestamp("Logger failed!");
	exit(1);
    }
}
