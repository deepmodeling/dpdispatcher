#!/usr/bin/env python
import argparse
from typing import List, Optional

from dpdispatcher.entrypoints.gui import start_dpgui
from dpdispatcher.entrypoints.run import run
from dpdispatcher.entrypoints.submission import handle_submission


def main_parser() -> argparse.ArgumentParser:
    """Dpdispatcher commandline options argument parser.

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
    # backward
    parser_submission = subparsers.add_parser(
        "submission",
        help="Handle terminated submission.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser_submission.add_argument(
        "SUBMISSION_HASH",
        type=str,
        help="Submission hash to download.",
    )
    parser_submission_action = parser_submission.add_argument_group(
        "Actions",
        description="One or more actions to take on submission.",
    )
    parser_submission_action.add_argument(
        "--download-terminated-log",
        action="store_true",
        help="Download log files of terminated tasks.",
    )
    parser_submission_action.add_argument(
        "--download-finished-task",
        action="store_true",
        help="Download finished tasks.",
    )
    parser_submission_action.add_argument(
        "--clean",
        action="store_true",
        help="Clean submission.",
    )
    parser_submission_action.add_argument(
        "--reset-fail-count",
        action="store_true",
        help="Reset fail count of all jobs to zero.",
    )
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
    ##########################################
    # run
    parser_run = subparsers.add_parser(
        "run",
        help="Run a Python script.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser_run.add_argument(
        "filename",
        type=str,
        help="Python script to run. PEP 723 metadata should be contained in this file.",
    )
    return parser


def parse_args(args: Optional[List[str]] = None):
    """Dpdispatcher commandline options argument parsing.

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
    if args.command == "submission":
        handle_submission(
            submission_hash=args.SUBMISSION_HASH,
            download_terminated_log=args.download_terminated_log,
            download_finished_task=args.download_finished_task,
            clean=args.clean,
            reset_fail_count=args.reset_fail_count,
        )
    elif args.command == "gui":
        start_dpgui(
            port=args.port,
            bind_all=args.bind_all,
        )
    elif args.command == "run":
        run(filename=args.filename)
    elif args.command is None:
        pass
    else:
        raise RuntimeError(f"unknown command {args.command}")


if __name__ == "__main__":
    main()
