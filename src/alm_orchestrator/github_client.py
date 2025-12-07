"""GitHub API client for the ALM Orchestrator."""

import logging
import shutil
import subprocess
import tempfile
from github import Github
from alm_orchestrator.config import Config

logger = logging.getLogger(__name__)


# Git/GitHub constants
DEFAULT_BRANCH = "main"
CLONE_DEPTH = 1
TEMP_DIR_PREFIX = "alm-orchestrator-"
GITHUB_CLONE_URL_PATTERN = "https://{token}@github.com/{repo}.git"


class GitHubClient:
    """Client for interacting with GitHub API and git operations."""

    def __init__(self, config: Config):
        """Initialize GitHub client with configuration.

        Args:
            config: Application configuration containing GitHub credentials.
        """
        self._config = config
        self._github = Github(config.github_token)
        self._repo = self._github.get_repo(config.github_repo)

    def get_authenticated_clone_url(self) -> str:
        """Get clone URL with embedded auth token.

        Returns:
            HTTPS clone URL with token for authentication.
        """
        return GITHUB_CLONE_URL_PATTERN.format(
            token=self._config.github_token,
            repo=self._config.github_repo
        )

    def clone_repo(self, branch: str = DEFAULT_BRANCH) -> str:
        """Clone the repository to a temporary directory.

        Args:
            branch: Branch to clone. Defaults to DEFAULT_BRANCH.

        Returns:
            Path to the cloned repository working directory.

        Raises:
            subprocess.CalledProcessError: If git clone fails.
        """
        work_dir = tempfile.mkdtemp(prefix=TEMP_DIR_PREFIX)
        clone_url = self.get_authenticated_clone_url()

        logger.info(f"Cloning {self._config.github_repo} (branch: {branch}) to {work_dir}")
        subprocess.run(
            ["git", "clone", "--depth", str(CLONE_DEPTH), "--branch", branch, clone_url, work_dir],
            check=True,
            capture_output=True,
        )
        logger.debug(f"Clone completed: {work_dir}")

        return work_dir

    def create_branch(self, work_dir: str, branch_name: str) -> None:
        """Create and checkout a new branch.

        Args:
            work_dir: Path to the git repository.
            branch_name: Name of the branch to create.

        Raises:
            subprocess.CalledProcessError: If git checkout fails.
        """
        logger.info(f"Creating branch: {branch_name}")
        subprocess.run(
            ["git", "checkout", "-b", branch_name],
            cwd=work_dir,
            check=True,
            capture_output=True,
        )
        logger.debug(f"Branch created: {branch_name}")

    def commit_and_push(self, work_dir: str, branch: str, message: str) -> None:
        """Stage all changes, commit, and push to remote.

        Args:
            work_dir: Path to the git repository.
            branch: Branch name to push.
            message: Commit message.

        Raises:
            subprocess.CalledProcessError: If any git command fails.
        """
        logger.info(f"Staging all changes")
        subprocess.run(
            ["git", "add", "-A"],
            cwd=work_dir,
            check=True,
            capture_output=True,
        )

        logger.info(f"Committing: {message}")
        subprocess.run(
            ["git", "commit", "-m", message],
            cwd=work_dir,
            check=True,
            capture_output=True,
        )

        logger.info(f"Pushing branch: {branch}")
        subprocess.run(
            ["git", "push", "-u", "origin", branch],
            cwd=work_dir,
            check=True,
            capture_output=True,
        )
        logger.debug(f"Push completed: {branch}")

    def cleanup(self, work_dir: str) -> None:
        """Remove the temporary working directory.

        Args:
            work_dir: Path to remove.
        """
        logger.debug(f"Cleaning up work directory: {work_dir}")
        shutil.rmtree(work_dir, ignore_errors=True)

    def create_pull_request(
        self,
        branch: str,
        title: str,
        body: str,
        base: str = DEFAULT_BRANCH
    ):
        """Create a pull request.

        Args:
            branch: Head branch name.
            title: PR title.
            body: PR description body.
            base: Base branch to merge into. Defaults to DEFAULT_BRANCH.

        Returns:
            The created PullRequest object.
        """
        logger.info(f"Creating pull request: {branch} -> {base}")
        pr = self._repo.create_pull(
            title=title,
            body=body,
            head=branch,
            base=base
        )
        logger.info(f"Pull request created: #{pr.number}")
        return pr

    def add_pr_comment(self, pr_number: int, body: str) -> None:
        """Add a comment to a pull request.

        Args:
            pr_number: The PR number.
            body: Comment text (supports GitHub markdown).
        """
        logger.debug(f"Adding comment to PR #{pr_number}")
        pr = self._repo.get_pull(pr_number)
        pr.create_issue_comment(body)

    def get_pr_info(self, pr_number: int) -> dict:
        """Get PR information including head branch, changed files, and description.

        Args:
            pr_number: The PR number.

        Returns:
            Dict with keys: head_branch, base_branch, changed_files, title, body.
        """
        logger.debug(f"Getting PR info for #{pr_number}")
        pr = self._repo.get_pull(pr_number)
        changed_files = [f.filename for f in pr.get_files()]
        return {
            "head_branch": pr.head.ref,
            "base_branch": pr.base.ref,
            "changed_files": changed_files,
            "title": pr.title,
            "body": pr.body or "",
        }

    def get_pr_by_branch(self, branch: str):
        """Find an open PR for a given branch.

        Args:
            branch: The head branch name.

        Returns:
            PullRequest object if found, None otherwise.
        """
        logger.debug(f"Looking up PR for branch: {branch}")
        prs = self._repo.get_pulls(state="open", head=f"{self._config.github_owner}:{branch}")
        for pr in prs:
            if pr.head.ref == branch:
                logger.debug(f"Found PR #{pr.number} for branch: {branch}")
                return pr
        logger.debug(f"No PR found for branch: {branch}")
        return None
