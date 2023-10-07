#!/usr/bin/env python
import argparse
from typing import List, Optional

from dpdispatcher.gui import start_dpgui


def main_parser() -> argparse.ArgumentParser:
    """dpdispatcher commandline options argument parser.

    Notes
    -----
    This function is used by documentation.

    Returns
    -------
    argparse.ArgumentParser
        the argument parser
    """
    parser = argparse.ArgumentParser(
        description="dpdispatcher: Generate HPC scheduler systems jobs input scripts, submit these scripts to HPC systems, and poke until they finish",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    subparsers = parser.add_subparsers(title="Valid subcommands", dest="command")
    ##########################################
    # gui
    parser_gui = subparsers.add_parser(
        "gui",
        help="Serve DP-GUI.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser_gui.add_argument(
        "-p",
        "--port",
        type=int,
        default=6042,
        help="The port to serve DP-GUI on.",
    )
    parser_gui.add_argument(
        "--bind_all",
        action="store_true",
        help=(
            "Serve on all public interfaces. This will expose your DP-GUI instance "
            "to the network on both IPv4 and IPv6 (where available)."
        ),
    )


def parse_args(args: Optional[List[str]] = None):
    """dpdispatcher commandline options argument parsing.

    Parameters
    ----------
    args : List[str]
        list of command line arguments, main purpose is testing default option None
        takes arguments from sys.argv
    """
    parser = main_parser()

    parsed_args = parser.parse_args(args=args)
    if parsed_args.command is None:
        parser.print_help()

    return parsed_args


def main():
    args = parse_args()
    if args.command == "gui":
        start_dpgui(
            port=args.port,
            bind_all=args.bind_all,
        )
    elif args.command is None:
        pass
    else:
        raise RuntimeError(f"unknown command {args.command}")


if __name__ == "__main__":
    main()
