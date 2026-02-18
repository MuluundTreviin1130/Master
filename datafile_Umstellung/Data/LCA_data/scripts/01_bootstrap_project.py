from __future__ import annotations

import bw2data as bd
import bw2io as bi

PROJECT = "my_lca_project"


def main() -> None:
    if PROJECT not in bd.projects:
        bd.projects.create_project(PROJECT)
    bd.projects.set_current(PROJECT)

    print("Active project:", bd.projects.current)
    print("Projects dir:", bd.projects.dir)

    # Ensure core migrations exist (required by some bw2io workflows)
    from bw2io.migrations import create_core_migrations

    create_core_migrations()

    # Create (or recreate) biosphere3 FIRST. Do this once and do not delete it
    # afterwards; otherwise LCIA methods and LCI databases can get out of sync.
    bi.create_default_biosphere3(overwrite=True)

    print("Databases:", list(bd.databases))


if __name__ == "__main__":
    main()
