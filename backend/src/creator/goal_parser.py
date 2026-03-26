"""Advanced goal parser for extracting deployment parameters from natural language."""

import logging
import re
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


class GoalParser:
    """Parse natural language deployment goals to extract structured parameters."""

    # Cloud provider keywords
    CLOUD_KEYWORDS = {
        "aws": ["aws", "amazon", "ec2", "ecs", "lambda", "ecr"],
        "azure": ["azure", "microsoft", "aci", "acr", "app service"],
        "gcp": ["gcp", "google cloud", "google", "cloud run", "gcr", "gke"],
        "local": ["local", "localhost", "dev", "development"],
    }

    # Environment keywords
    ENVIRONMENT_KEYWORDS = {
        "production": ["production", "prod", "live", "main"],
        "staging": ["staging", "stage", "test", "qa"],
        "development": ["dev", "development", "local", "debug"],
    }

    # Deployment strategy keywords
    STRATEGY_KEYWORDS = {
        "blue_green": ["blue-green", "blue green", "bluegreen"],
        "canary": ["canary"],
        "rolling": ["rolling"],
        "recreate": ["recreate"],
    }

    # AWS regions
    AWS_REGIONS = [
        "us-east-1", "us-east-2", "us-west-1", "us-west-2",
        "eu-west-1", "eu-west-2", "eu-central-1",
        "ap-southeast-1", "ap-southeast-2", "ap-northeast-1",
        "ca-central-1", "sa-east-1"
    ]

    # Azure regions
    AZURE_REGIONS = [
        "eastus", "eastus2", "westus", "westus2", "westus3",
        "northcentralus", "southcentralus", "centralus",
        "northeurope", "westeurope", "uksouth", "ukwest",
        "japaneast", "japanwest", "southeastasia", "eastasia"
    ]

    # GCP regions
    GCP_REGIONS = [
        "us-central1", "us-east1", "us-east4", "us-west1", "us-west2", "us-west3", "us-west4",
        "europe-west1", "europe-west2", "europe-west3", "europe-west4", "europe-west6",
        "asia-east1", "asia-east2", "asia-northeast1", "asia-northeast2", "asia-northeast3",
        "asia-south1", "asia-southeast1", "asia-southeast2"
    ]

    def parse(self, goal: str) -> Dict[str, Any]:
        """Parse goal and extract deployment parameters.
        
        Args:
            goal: Natural language deployment goal
            
        Returns:
            Dictionary with extracted parameters:
            - cloud: Cloud provider (aws, azure, gcp, local)
            - environment: Deployment environment (production, staging, development)
            - region: Cloud region
            - strategy: Deployment strategy (blue_green, canary, rolling, recreate)
            - is_valid: Whether goal is valid and feasible
            - error_message: Error message if invalid
        """
        goal_lower = goal.lower()

        return {
            "cloud": self._extract_cloud(goal_lower),
            "environment": self._extract_environment(goal_lower),
            "region": self._extract_region(goal_lower),
            "strategy": self._extract_strategy(goal_lower),
            "is_valid": self._validate_goal(goal_lower),
            "error_message": self._get_error_message(goal_lower),
        }

    def _extract_cloud(self, goal: str) -> str:
        """Extract cloud provider from goal.
        
        Args:
            goal: Lowercase goal string
            
        Returns:
            Cloud provider name (aws, azure, gcp, local)
        """
        for cloud, keywords in self.CLOUD_KEYWORDS.items():
            for keyword in keywords:
                if keyword in goal:
                    logger.debug(f"Detected cloud provider: {cloud}")
                    return cloud
        return "local"

    def _extract_environment(self, goal: str) -> str:
        """Extract environment from goal.
        
        Args:
            goal: Lowercase goal string
            
        Returns:
            Environment name (production, staging, development)
        """
        for env, keywords in self.ENVIRONMENT_KEYWORDS.items():
            for keyword in keywords:
                if keyword in goal:
                    logger.debug(f"Detected environment: {env}")
                    return env
        return "staging"

    def _extract_region(self, goal: str) -> str:
        """Extract region from goal.
        
        Args:
            goal: Lowercase goal string
            
        Returns:
            Region name or default
        """
        # Try AWS regions
        for region in self.AWS_REGIONS:
            if region in goal:
                logger.debug(f"Detected AWS region: {region}")
                return region

        # Try Azure regions
        for region in self.AZURE_REGIONS:
            if region in goal:
                logger.debug(f"Detected Azure region: {region}")
                return region

        # Try GCP regions
        for region in self.GCP_REGIONS:
            if region in goal:
                logger.debug(f"Detected GCP region: {region}")
                return region

        # Try generic region pattern (e.g., "us-east-1", "eu-west-1")
        match = re.search(r"([a-z]+-[a-z]+-\d+)", goal)
        if match:
            region = match.group(1)
            logger.debug(f"Detected region from pattern: {region}")
            return region

        # Default based on cloud
        cloud = self._extract_cloud(goal)
        if cloud == "aws":
            return "us-east-1"
        elif cloud == "azure":
            return "eastus"
        elif cloud == "gcp":
            return "us-central1"
        else:
            return "local"

    def _extract_strategy(self, goal: str) -> str:
        """Extract deployment strategy from goal.
        
        Args:
            goal: Lowercase goal string
            
        Returns:
            Strategy name (blue_green, canary, rolling, recreate)
        """
        for strategy, keywords in self.STRATEGY_KEYWORDS.items():
            for keyword in keywords:
                if keyword in goal:
                    logger.debug(f"Detected deployment strategy: {strategy}")
                    return strategy
        return "rolling"

    def _validate_goal(self, goal: str) -> bool:
        """Check if goal is valid and feasible.
        
        Args:
            goal: Lowercase goal string
            
        Returns:
            True if goal is valid, False otherwise
        """
        # Must contain action verb
        actions = ["deploy", "run", "start", "release", "publish", "push"]
        has_action = any(action in goal for action in actions)

        if not has_action:
            logger.warning("Goal does not contain action verb")
            return False

        # Check for conflicting clouds
        clouds_found = 0
        if "aws" in goal or "amazon" in goal:
            clouds_found += 1
        if "azure" in goal or "microsoft" in goal:
            clouds_found += 1
        if "gcp" in goal or "google" in goal:
            clouds_found += 1

        if clouds_found > 1:
            logger.warning("Goal contains multiple cloud providers")
            return False

        # Check for conflicting environments
        envs_found = 0
        if "production" in goal or "prod" in goal or "live" in goal or "main" in goal:
            envs_found += 1
        if "staging" in goal or "stage" in goal or "test" in goal or "qa" in goal:
            envs_found += 1
        if "dev" in goal or "development" in goal or "debug" in goal:
            envs_found += 1

        if envs_found > 1:
            logger.warning("Goal contains multiple environments")
            return False

        return True

    def _get_error_message(self, goal: str) -> Optional[str]:
        """Return helpful error message if goal is invalid.
        
        Args:
            goal: Lowercase goal string
            
        Returns:
            Error message or None if valid
        """
        # Check for missing action
        actions = ["deploy", "run", "start", "release", "publish", "push"]
        if not any(action in goal for action in actions):
            return "Goal must include action: deploy, run, start, release, publish, or push"

        # Check for conflicting clouds
        clouds_found = []
        if "aws" in goal or "amazon" in goal:
            clouds_found.append("AWS")
        if "azure" in goal or "microsoft" in goal:
            clouds_found.append("Azure")
        if "gcp" in goal or "google" in goal:
            clouds_found.append("GCP")

        if len(clouds_found) > 1:
            return f"Goal cannot target multiple clouds: {', '.join(clouds_found)}"

        # Check for conflicting environments
        envs_found = []
        if "production" in goal or "prod" in goal:
            envs_found.append("production")
        if "staging" in goal or "stage" in goal:
            envs_found.append("staging")
        if "dev" in goal or "development" in goal:
            envs_found.append("development")

        if len(envs_found) > 1:
            return f"Goal cannot target multiple environments: {', '.join(envs_found)}"

        return None


def parse_goal(goal: str) -> Dict[str, Any]:
    """Parse a deployment goal using GoalParser.
    
    Args:
        goal: Natural language deployment goal
        
    Returns:
        Dictionary with extracted parameters
    """
    parser = GoalParser()
    return parser.parse(goal)
