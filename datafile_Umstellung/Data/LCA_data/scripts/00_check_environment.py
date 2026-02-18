from __future__ import annotations

import sys

import bw2data as bd

PROJECT = "my_lca_project"


def main() -> int:
    bd.projects.set_current(PROJECT)
    print("Python:", sys.version)
    print("Project:", bd.projects.current)
    print("Projects dir:", bd.projects.dir)
    print("Databases:", list(bd.databases))
    print("Methods:", len(list(bd.methods)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
