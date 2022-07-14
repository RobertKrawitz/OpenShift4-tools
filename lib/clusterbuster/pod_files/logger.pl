#!/usr/bin/perl

use Socket;
use POSIX;
use strict;
use Time::Piece;
use Time::HiRes qw(gettimeofday usleep);
use Sys::Hostname;
use File::Basename;
use Getopt::Long;
Getopt::Long::Configure('bundling', 'no_ignore_case', 'pass_through');
my ($dir) = $ENV{'BAK_CONFIGMAP'};
require "$dir/clientlib.pl";

$SIG{TERM} = sub { POSIX::_exit(0); };
my ($basetime, $baseoffset, $crtime, $synchost, $syncport, $namespace, $container, $bytes_per_line, $bytes_per_io, $xfer_count, $processes, $delay_usecs, $xfer_time, $exit_at_end);

GetOptions('n=s' => \$namespace,
	   'namespace=s' => \$namespace,
	   'c=s' => \$container,
	   'container=s' => \$container,
	   'basetime=f' => \$basetime,
	   'baseoffset=f' => \$baseoffset,
	   'crtime=f' => \$crtime,
	   'exit_at_end!' => \$exit_at_end,
	   'synchost=s' => \$synchost,
	   'sync_host=s' => \$synchost,
	   'syncport=i' => \$syncport,
	   'sync_port=i' => \$syncport,
	   'processes=i' => \$processes,
	   'xfer_time=i' => \$xfer_time,
	   'bytes_per_line' => \$bytes_per_line,
	   'bytes_per_io' => \$bytes_per_io,
	   'xfer_count' => \$xfer_count,
	   'delay_usecs' => \$delay_usecs,
    );

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
}
