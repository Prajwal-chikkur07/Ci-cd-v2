import logging
import re
import shutil
import tempfile
from typing import Optional

import git

from src.config import settings
from src.creator.detector import detect_language
from src.models.pipeline import RepoAnalysis

logger = logging.getLogger(__name__)


def detect_deploy_target(goal: str) -> Optional[str]:
    """Parse the goal string to detect a deployment target."""
    goal_lower = goal.lower()
    targets = {
        "aws": "aws",
        "gcp": "gcp",
        "google cloud": "gcp",
        "azure": "azure",
        "docker": "docker",
        "heroku": "heroku",
        "kubernetes": "kubernetes",
        "k8s": "kubernetes",
    }
    for keyword, target in targets.items():
        if keyword in goal_lower:
            return target
    if "staging" in goal_lower:
        return "staging"
    if "production" in goal_lower or "prod" in goal_lower:
        return "production"
    return None


async def analyze_repo(repo_url: str, goal: str = "") -> tuple[RepoAnalysis, str]:
    """Clone a repository and analyze its structure.

    Clones the repo into a temporary directory and runs detection.
    Returns the analysis and the clone path (caller is responsible
    for cleanup).
    """
    tmp_dir = tempfile.mkdtemp(prefix="cicd-analyzer-")
    try:
        # Convert SSH URL to HTTPS
        if repo_url.startswith("git@"):
            repo_url = repo_url.replace(":", "/").replace("git@", "https://")

        # Inject GitHub token for private repos
        authenticated_url = repo_url
        if settings.github_token and "github.com" in repo_url:
            authenticated_url = re.sub(
                r"https://github\.com",
                f"https://{settings.github_token}@github.com",
                repo_url,
            )

        logger.info("Cloning %s into %s", repo_url, tmp_dir)
        git.Repo.clone_from(authenticated_url, tmp_dir, depth=1)
        logger.info("Clone complete, running analysis")
        analysis = detect_language(tmp_dir)

        # Detect deploy target from goal
        if goal:
            deploy_target = detect_deploy_target(goal)
            if deploy_target:
                analysis.deploy_target = deploy_target
                logger.info("Detected deploy target: %s", deploy_target)

        logger.info(
            "Analysis complete: language=%s framework=%s deploy_target=%s",
            analysis.language,
            analysis.framework,
            analysis.deploy_target,
        )
        return analysis, tmp_dir
    except git.GitCommandError as e:
        logger.error("Failed to clone repository: %s", e)
        shutil.rmtree(tmp_dir, ignore_errors=True)
        raise ValueError(f"Failed to clone repository: {e}") from e
