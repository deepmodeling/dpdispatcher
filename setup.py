"""Bundle the canonical public workflow guides in binary distributions."""

import shutil
from pathlib import Path

from setuptools import setup
from setuptools.command.build_py import build_py


class BuildPy(build_py):
    """Copy public skill resources without maintaining a second source tree."""

    def run(self) -> None:
        """Build Python modules and include the version-matched guides."""
        super().run()
        destination = Path(self.build_lib) / "dpdispatcher" / "_skills"
        if destination.exists():
            shutil.rmtree(destination)
        source = Path(__file__).parent / "skills"
        for path in source.rglob("*"):
            if path.is_file() and not path.is_symlink():
                target = (
                    Path(self.build_lib)
                    / "dpdispatcher"
                    / "_skills"
                    / path.relative_to(source)
                )
                self.mkpath(str(target.parent))
                self.copy_file(str(path), str(target))


setup(cmdclass={"build_py": BuildPy})
