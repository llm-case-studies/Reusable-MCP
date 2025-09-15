#!/usr/bin/env python3
import argparse
import sys
import time
import json

def main():
    p = argparse.ArgumentParser(description='Probe script for Test-Start-MCP')
    p.add_argument('--repeat', type=int, default=3, help='number of stdout lines to print')
    p.add_argument('--stderr-lines', type=int, default=1, help='number of stderr lines to print')
    p.add_argument('--sleep-ms', type=int, default=100, help='sleep between lines (ms)')
    p.add_argument('--bytes', type=int, default=0, help='emit a blob of N bytes on stdout at end')
    p.add_argument('--exit-code', type=int, default=0, help='exit code to return')
    p.add_argument('--json', action='store_true', help='emit a final JSON line')
    p.add_argument('--ping', action='store_true', help='print ping ticks')
    p.add_argument('--smoke', action='store_true', help='quick smoke: 2 lines out, 1 err')
    args = p.parse_args()

    rep = args.repeat
    errn = args.stderr_lines
    slp = max(0, args.sleep_ms) / 1000.0
    if args.smoke:
        rep = 2
        errn = 1
        slp = 0.05

    for i in range(rep):
        print(f"probe: line {i+1}/{rep}")
        if args.ping:
            print(f"probe: ping {i}")
        sys.stdout.flush()
        time.sleep(slp)

    for j in range(errn):
        print(f"probe: warn {j+1}/{errn}", file=sys.stderr)
        sys.stderr.flush()
        time.sleep(slp)

    if args.bytes and args.bytes > 0:
        sys.stdout.write('X' * args.bytes + '\n')
        sys.stdout.flush()

    if args.json:
        obj = {
            'ok': args.exit_code == 0,
            'repeat': rep,
            'stderr_lines': errn,
            'sleep_ms': int(slp*1000),
        }
        print(json.dumps(obj))
        sys.stdout.flush()

    return sys.exit(int(args.exit_code))

if __name__ == '__main__':
    main()

