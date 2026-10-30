"""Help and version interface for the workbench foundation."""

import argparse
import sys

from research_pipeline import __version__


def main(argv=None):
    """Print foundation help or version; invalid arguments exit with usage status 2."""
    parser = argparse.ArgumentParser(
        description="Research workbench foundation: research execution is unavailable.",
        allow_abbrev=False,
    )
    parser.add_argument("--version", action="version", version=__version__)
    arguments = sys.argv[1:] if argv is None else argv
    parser.parse_args(arguments)
    parser.print_help()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
