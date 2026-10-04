"""Usage:
python -m seraph.guard scan --path .
python -m seraph.guard scan --path . --explain
python -m seraph.guard status
"""

from seraph.guard.cli import main


if __name__ == "__main__":
    main()
