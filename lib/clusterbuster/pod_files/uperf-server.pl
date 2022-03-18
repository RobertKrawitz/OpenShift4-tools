#!/usr/bin/perl
use Socket;
use POSIX;
use strict;
use Time::Piece;
use Time::HiRes qw(gettimeofday usleep);
use File::Basename;
my ($dir) = $ENV{'BAK_CONFIGMAP'};
require "$dir/clientlib.pl";

$SIG{TERM} = sub { POSIX::_exit(0); };
my ($basetime, $baseoffset, $listen_port) = @ARGV;
$basetime += $baseoffset;
$SIG{CHLD} = 'IGNORE';

timestamp("Starting uperf server");
system("uperf", "-s", "-v", "-P", "$listen_port");
timestamp("Done!");

finish(1);
