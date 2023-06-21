#!/usr/bin/env python3

import argparse

from index import scan

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--debug", action = "store_true",
                        help = "just debugging scan")
    args = parser.parse_args()
    scan(debug = args.debug)


if __name__ == "__main__":
    main()
