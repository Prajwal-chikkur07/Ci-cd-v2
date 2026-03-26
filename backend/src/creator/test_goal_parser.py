"""Unit tests for goal parser."""

import pytest

from src.creator.goal_parser import GoalParser, parse_goal


class TestGoalParser:
    """Test GoalParser class."""

    def test_parse_aws_production(self):
        """Test parsing AWS production deployment goal."""
        parser = GoalParser()
        result = parser.parse("deploy to AWS production")

        assert result["cloud"] == "aws"
        assert result["environment"] == "production"
        assert result["is_valid"] is True
        assert result["error_message"] is None

    def test_parse_azure_staging(self):
        """Test parsing Azure staging deployment goal."""
        parser = GoalParser()
        result = parser.parse("deploy to Azure staging")

        assert result["cloud"] == "azure"
        assert result["environment"] == "staging"
        assert result["is_valid"] is True

    def test_parse_gcp_development(self):
        """Test parsing GCP development deployment goal."""
        parser = GoalParser()
        result = parser.parse("deploy to Google Cloud development")

        assert result["cloud"] == "gcp"
        assert result["environment"] == "development"
        assert result["is_valid"] is True

    def test_parse_local_dev(self):
        """Test parsing local development deployment goal."""
        parser = GoalParser()
        result = parser.parse("run locally for dev")

        assert result["cloud"] == "local"
        assert result["environment"] == "development"
        assert result["is_valid"] is True

    def test_parse_with_region_aws(self):
        """Test parsing goal with AWS region."""
        parser = GoalParser()
        result = parser.parse("deploy to AWS us-west-2 production")

        assert result["cloud"] == "aws"
        assert result["region"] == "us-west-2"
        assert result["environment"] == "production"

    def test_parse_with_region_azure(self):
        """Test parsing goal with Azure region."""
        parser = GoalParser()
        result = parser.parse("deploy to Azure westus staging")

        assert result["cloud"] == "azure"
        assert result["region"] == "westus"

    def test_parse_with_region_gcp(self):
        """Test parsing goal with GCP region."""
        parser = GoalParser()
        result = parser.parse("deploy to GCP europe-west1 production")

        assert result["cloud"] == "gcp"
        assert result["region"] == "europe-west1"

    def test_parse_with_blue_green_strategy(self):
        """Test parsing goal with blue-green deployment strategy."""
        parser = GoalParser()
        result = parser.parse("deploy to AWS with blue-green strategy")

        assert result["strategy"] == "blue_green"

    def test_parse_with_canary_strategy(self):
        """Test parsing goal with canary deployment strategy."""
        parser = GoalParser()
        result = parser.parse("deploy to AWS with canary strategy")

        assert result["strategy"] == "canary"

    def test_parse_with_rolling_strategy(self):
        """Test parsing goal with rolling deployment strategy."""
        parser = GoalParser()
        result = parser.parse("deploy to AWS with rolling strategy")

        assert result["strategy"] == "rolling"

    def test_parse_default_values(self):
        """Test parsing with minimal goal uses defaults."""
        parser = GoalParser()
        result = parser.parse("deploy")

        assert result["cloud"] == "local"
        assert result["environment"] == "staging"
        assert result["strategy"] == "rolling"

    def test_parse_invalid_no_action(self):
        """Test parsing goal without action verb."""
        parser = GoalParser()
        result = parser.parse("AWS production")

        assert result["is_valid"] is False
        assert "action" in result["error_message"].lower()

    def test_parse_invalid_multiple_clouds(self):
        """Test parsing goal with multiple clouds."""
        parser = GoalParser()
        result = parser.parse("deploy to AWS and Azure")

        assert result["is_valid"] is False
        assert "multiple clouds" in result["error_message"].lower()

    def test_parse_invalid_multiple_environments(self):
        """Test parsing goal with multiple environments."""
        parser = GoalParser()
        result = parser.parse("deploy to production and staging")

        assert result["is_valid"] is False
        assert "multiple environments" in result["error_message"].lower()

    def test_parse_case_insensitive(self):
        """Test parsing is case insensitive."""
        parser = GoalParser()
        result1 = parser.parse("DEPLOY TO AWS PRODUCTION")
        result2 = parser.parse("deploy to aws production")

        assert result1["cloud"] == result2["cloud"]
        assert result1["environment"] == result2["environment"]

    def test_parse_with_various_action_verbs(self):
        """Test parsing with different action verbs."""
        parser = GoalParser()

        for action in ["deploy", "run", "start", "release", "publish", "push"]:
            result = parser.parse(f"{action} to AWS")
            assert result["is_valid"] is True

    def test_parse_aws_regions(self):
        """Test parsing various AWS regions."""
        parser = GoalParser()
        regions = ["us-east-1", "us-west-2", "eu-west-1", "ap-southeast-1"]

        for region in regions:
            result = parser.parse(f"deploy to AWS {region}")
            assert result["region"] == region

    def test_parse_azure_regions(self):
        """Test parsing various Azure regions."""
        parser = GoalParser()
        regions = ["eastus", "westus", "northeurope", "westeurope"]

        for region in regions:
            result = parser.parse(f"deploy to Azure {region}")
            assert result["region"] == region

    def test_parse_gcp_regions(self):
        """Test parsing various GCP regions."""
        parser = GoalParser()
        regions = ["us-central1", "europe-west1", "asia-east1"]

        for region in regions:
            result = parser.parse(f"deploy to GCP {region}")
            assert result["region"] == region

    def test_parse_complex_goal(self):
        """Test parsing complex goal with multiple parameters."""
        parser = GoalParser()
        result = parser.parse(
            "deploy to AWS us-west-2 production with blue-green strategy"
        )

        assert result["cloud"] == "aws"
        assert result["region"] == "us-west-2"
        assert result["environment"] == "production"
        assert result["strategy"] == "blue_green"
        assert result["is_valid"] is True

    def test_parse_goal_function(self):
        """Test module-level parse_goal function."""
        result = parse_goal("deploy to AWS staging")

        assert result["cloud"] == "aws"
        assert result["environment"] == "staging"
        assert result["is_valid"] is True

    def test_extract_cloud_with_service_names(self):
        """Test cloud extraction with service names."""
        parser = GoalParser()

        # AWS services
        result = parser.parse("deploy to ECS")
        assert result["cloud"] == "aws"

        # Azure services
        result = parser.parse("deploy to ACI")
        assert result["cloud"] == "azure"

        # GCP services
        result = parser.parse("deploy to Cloud Run")
        assert result["cloud"] == "gcp"

    def test_parse_production_variations(self):
        """Test parsing production environment with variations."""
        parser = GoalParser()

        for prod_keyword in ["production", "prod", "live", "main"]:
            result = parser.parse(f"deploy to AWS {prod_keyword}")
            assert result["environment"] == "production"

    def test_parse_staging_variations(self):
        """Test parsing staging environment with variations."""
        parser = GoalParser()

        for staging_keyword in ["staging", "stage", "test", "qa"]:
            result = parser.parse(f"deploy to AWS {staging_keyword}")
            assert result["environment"] == "staging"

    def test_parse_dev_variations(self):
        """Test parsing development environment with variations."""
        parser = GoalParser()

        for dev_keyword in ["dev", "development", "local", "debug"]:
            result = parser.parse(f"deploy to {dev_keyword}")
            assert result["environment"] == "development"

    def test_default_region_by_cloud(self):
        """Test default region selection based on cloud provider."""
        parser = GoalParser()

        result = parser.parse("deploy to AWS")
        assert result["region"] == "us-east-1"

        result = parser.parse("deploy to Azure")
        assert result["region"] == "eastus"

        result = parser.parse("deploy to GCP")
        assert result["region"] == "us-central1"

        result = parser.parse("deploy locally")
        assert result["region"] == "local"
