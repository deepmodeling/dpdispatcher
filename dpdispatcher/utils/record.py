import json
from pathlib import Path
from typing import List


class Record:
    """Record failed or canceled submissions."""

    def __init__(self) -> None:
        self.record_directory = Path.home() / ".dpdispatcher" / "submission"
        self.record_directory.mkdir(parents=True, exist_ok=True)

    def get_submissions(self) -> List[str]:
        """Get all stored submission hashes.

        Returns
        -------
        list[str]
            List of submission hashes.
        """
        return [
            f.stem
            for f in self.record_directory.iterdir()
            if (f.is_file() and f.suffix == ".json")
        ]

    def write(self, submission) -> Path:
        """Write submission data to file.

        Parameters
        ----------
        submission : dpdispatcher.Submission
            Submission data.

        Returns
        -------
        pathlib.Path
            Path to submission data.
        """
        submission_path = self.record_directory / f"{submission.submission_hash}.json"
        submission_path.write_text(json.dumps(submission.serialize(), indent=2))
        return submission_path

    def get_submission(self, hash: str, not_exist_ok: bool = False) -> Path:
        """Get submission data by hash.

        Parameters
        ----------
        hash : str
            Hash of submission data.

        Returns
        -------
        pathlib.Path
            Path to submission data.
        """
        submission_file = self.record_directory / f"{hash}.json"
        if not not_exist_ok and not submission_file.is_file():
            raise FileNotFoundError(f"Submission file not found: {submission_file}")
        return submission_file

    def remove(self, hash: str):
        """Remove submission data by hash.

        Call this method when the remote directory is cleaned.

        Parameters
        ----------
        hash : str
            Hash of submission data.
        """
        path = self.get_submission(hash, not_exist_ok=True)
        if path.is_file():
            path.unlink()


# the record object can be globally used
record = Record()
__all__ = ["record"]
