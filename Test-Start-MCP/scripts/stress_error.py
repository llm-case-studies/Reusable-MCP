#!/usr/bin/env python3
import sys
import time

# A simple script to generate a lot of stderr output for testing.

def main():
    num_lines = 1000
    for i in range(num_lines):
        print(f"This is stderr line {i+1}", file=sys.stderr)
        time.sleep(0.01)
    print("Finished writing to stderr.", file=sys.stdout)

if __name__ == "__main__":
    main()
