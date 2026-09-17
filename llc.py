#!/usr/bin/env python3

from compiler.output import output_file
from compiler.compile import compile
from compiler.optim import optimize
import compiler.defs as defs

import argparse


parser = argparse.ArgumentParser(description="Cream Compiler")
# input_file expected to be a .li file
parser.add_argument("input_file",           help="Input file to compile",  type=str)
parser.add_argument("-a", "--dump-asm",     help="Dump assembly code to stdout", action="store_true", dest="dump_asm")
parser.add_argument("-o", "--output",       help="Output file name",       default="output.bin", dest="output_file")
parser.add_argument("-n", "--no-opti",      help="Disable optimizations",  action="store_true",  dest="no_opti")
parser.add_argument("-v", "--verbose",      help="Verbose output",         action="store_true",  dest="verbose")
parser.add_argument("-x", "--extra-errors", help="Add boring code checks", action="store_true",  dest="extra_err")
args = parser.parse_args()

defs.EXTRAERR = args.extra_err
defs.VERBOSE  = args.verbose

try:
    with open(args.input_file, "r") as ifile:
        lines = ifile.read()
except FileNotFoundError:
    exit(f"Could not open input file: {args.input_file}")

main_output = compile(lines, args.input_file)

if not args.no_opti:
    main_output = optimize(main_output)

if args.dump_asm:
    main_output.dump()
    print("\n")

main_output.resolve_labels()
# main_output.dump(hide_labels = True)

output = output_file()
output.add_section(0, output_file.section.TYPE_CODE, main_output.to_bytes())
if defs.STATIC_BYTES:
    output.add_section(defs.STATIC_ADDR, output_file.section.TYPE_DATA, defs.STATIC_BYTES)

ofile = open(args.output_file, "wb")

if not ofile:
    exit("Could not open output file")

output.write(ofile)
