#!/usr/bin/env python

"""Commits the current renders with USD + luxtest repo information added"""

import argparse
import inspect
import os
import subprocess
import sys
import tempfile
import traceback

from typing import Iterable

###############################################################################
# Constants
###############################################################################

THIS_FILE = os.path.abspath(inspect.getsourcefile(lambda: None) or __file__)
THIS_DIR = os.path.dirname(THIS_FILE)

RENDERS_REPO = THIS_DIR
LUXTEST_REPO = os.path.dirname(THIS_DIR)

DEFAULT_USD_REPO = os.path.join(os.path.dirname(LUXTEST_REPO), "usd-ci", "USD")
USD_REPO = os.environ.get("USD_ROOT", DEFAULT_USD_REPO)

REPO_NAMES_TO_DIRS = {
    "USD": USD_REPO,
    "luxtest": LUXTEST_REPO,
}

###############################################################################
# Utilities
###############################################################################


def is_ipython():
    try:
        __IPYTHON__  # type: ignore
    except NameError:
        return False
    return True


def git(repo_dir, args, check=True, **kwargs):
    full_args = ["git"] + list(args)
    print(repo_dir)
    print(full_args)
    return subprocess.run(full_args, cwd=repo_dir, check=check, **kwargs)


def git_stdout(repo_dir, args, **kwargs):
    kwargs["text"] = True
    kwargs["capture_output"] = True
    proc = git(repo_dir, args, **kwargs)
    return proc.stdout.strip()


def get_git_hash(repo_dir, commit="HEAD"):
    return git_stdout(repo_dir, ["rev-parse", commit])


def git_commit_subject(repo_dir, commit="HEAD"):
    return git_stdout(repo_dir, ["log", "-1", "--format=%s", commit])


def get_repo_info(repo_name):
    repo_dir = REPO_NAMES_TO_DIRS[repo_name]
    commit_hash = get_git_hash(repo_dir)
    message_subject = git_commit_subject(repo_dir)

    return f"{repo_name}:\n{message_subject}\n{commit_hash}"


###############################################################################
# Core functions
###############################################################################


def commit_renders(message="", extra_paths: Iterable[str] = ()):
    message_parts = [get_repo_info(name) for name in REPO_NAMES_TO_DIRS]

    # we will add commit info, but we require some custom description as well
    # if they don't specify a mes-asage, git should fire up an editor, with a
    # custom template we provide

    commit_args = ["commit", "-a"]
    # if extra_paths are relative, assume they're relative to cwd (so
    # user can make use of shell completion)
    cwd = os.getcwd()
    commit_args.extend(os.path.join(cwd, p) for p in extra_paths)

    if message:
        # we can compute the full message + commit immediately
        message_parts.insert(0, message)
        full_message = "\n\n".join(message_parts)
        commit_args[1:1] = ["-m", full_message]
        git(RENDERS_REPO, commit_args)
        return

    # we set a commit template, so user can fill in the full message
    # themselves
    with tempfile.TemporaryDirectory(prefix="luxtest_renders_commit") as tempd:
        template_path = os.path.join(tempd, "git_commit_template.txt")
        message_parts.insert(0, "<insert custom message here>")
        full_message = "\n\n".join(message_parts)
        with open(template_path, "w", encoding="utf8") as writer:
            writer.write(full_message)
        commit_args[0:0] = ["-c", f"commit.template={template_path}"]
        git(RENDERS_REPO, commit_args)


###############################################################################
# CLI
###############################################################################


def get_parser():
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument(
        "-m",
        "--message",
        default="",
        help=(
            "Extra commit message; if not given, an editor with a pre-filled "
            "template will be opened"
        ),
    )
    parser.add_argument(
        "extra_paths",
        nargs="*",
        help=(
            "not-yet-commited paths to add to commit (all modified paths "
            "already in the repo are always committed, like 'commit -a')"
        ),
    )
    return parser


def main(argv=None):
    if argv is None:
        argv = sys.argv[1:]
    parser = get_parser()
    args = parser.parse_args(argv)
    try:
        commit_renders(message=args.message, extra_paths=args.extra_paths)
    except Exception:  # pylint: disable=broad-except

        traceback.print_exc()
        return 1
    return 0


if __name__ == "__main__" and not is_ipython():
    sys.exit(main())
