"""
Run a command transforming its output to the specified format,
and exiting with the same exit code as the original command.

The output is printed in stdout even if it came from stderr, to
preserve the order when capturing it with subprocess.

Example
-------
$ azurify.py -d : -o "[err={2};file={0}]" -- echo "test.py:124:not found:xxx"
[err=not found;file=test.py]
"""
import argparse
import os
import subprocess
import sys


def run_command_replacing_output(command):
    res = subprocess.run(args, stdout=sys.stdout, stderr=subprocess.STDOUT)
    return res.returncode


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description="Reformat output for azure.")
    parser.add_argument("command", help="command to execute")
    parser.add_argument(
        "-d", "--delimiter", type=str, default=None, help="character to split the input"
    )
    parser.add_argument(
        "-o", "--output", type=str, default="{0}",
        help="format of the ouput, use {0}, {1} for fields from the input"
    )
    parser.add_argument(
        "-r", "--reverse", action='store_true',
        help="make exit code the opposite as the returned by the command"
    )
    args = parser.parse_args()
    if os.environ.get('AZURE') != 'true':
        # TODO convert command to args
        exit_code = subprocess.run(args.command).returncode
    else:
        exit_code = run_command_replacing_output(args.command)

    sys.exit(not exit_code if args.reverse else exit_code)
