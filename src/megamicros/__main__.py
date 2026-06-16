#!/usr/bin/env python3
# -*- coding: utf-8 -*-


import sys
import argparse


parser = argparse.ArgumentParser(description="Megamicros : Recording using command-line tool.")
parser.add_argument(
    'version', metavar='version', 
    type=int,
    help='Version of the used system (32, 128, 256 or 1024 channels)',
)
parser.add_argument(
    "-d", "--duration", metavar="duration", type=int, default=5,
    help="Duration of acquisition [per default : 5 secondes]",
)
parser.add_argument(
    "-n", "--name", metavar="name", type=str, default="recording",
    help="Name of the output file [per default : see documentation]",
)
parser.add_argument(
    "-c", "--channels", metavar="channels", type=int,
    help="Number of microphone channels to use [per default : see documentation]",
)
parser.add_argument(
    "-a", "--analogs", metavar="analogs", type=int, default=0,
    help="Number of analog channels to use [per default : 0]",
)
parser.add_argument(
    "-m", "--message", metavar="message", type=str, default="",
    help="Comments to save about the recording",
)
parser.add_argument(
    "--usb", metavar="version_usb", dest="version_usb", 
    type=int, default=3,
    help="USB version (2 ou 3) [per default : 3]",
)
parser.add_argument(
    "-v", "--verbose", action="store_true",
    help="Verbose mode [per default : disabled]",
)


def main():
    args = parser.parse_args()
    
    # test if verbose mode
    if args.verbose:
        verbose = True
    else:
        verbose = False
    
    # maximum number of channels allowed by the system
    if args.channels:
        channels = args.channels
    else:
        channels = args.version
    
    if args.version_usb == 3:
        from megamicros.system import run
        run(args.version,
            channels,
            args.analogs,
            args.duration,
            args.name,
            args.message,
            verbose)


if __name__ == "__main__":
    sys.exit(main())
