"""Integration tests for Phase 3: Cloud Deployment, Rollback, and Goal Parsing."""

import json
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.creator.goal_parser import GoalParser, parse_goal
from src.executor.cloud_adapters import (
    AWSAdapter,
    AzureAdapter,
    CloudProvider,
    GCPAdapter,
    get_cloud_adapter,
)
from src.models.pipeline import DeploymentVersion


class TestPhase3Integration:
    """Integration tests for Phase 3 components."""

    def test_goal_parser_with_cloud_adapter_selection(self):
        """Test goal parsing leads to correct cloud adapter selection."""
        parser = GoalParser()

        # AWS goal
        result = parser.parse("deploy to AWS us-west-2 production")
        assert result["cloud"] == "aws"
        adapter = get_cloud_adapter(result["cloud"], result["region"], result["environment"])
        assert isinstance(adapter, AWSAdapter)
        assert adapter.region == "us-west-2"
        assert adapter.environment == "production"

        # Azure goal
        result = parser.parse("deploy to Azure westus staging")
        assert result["cloud"] == "azure"
        adapter = get_cloud_adapter(result["cloud"], result["region"], result["environment"])
        assert isinstance(adapter, AzureAdapter)
        assert adapter.region == "westus"
        assert adapter.environment == "staging"

        # GCP goal
        result = parser.parse("deploy to GCP europe-west1 development")
        assert result["cloud"] == "gcp"
        adapter = get_cloud_adapter(result["cloud"], result["region"], result["environment"])
        assert isinstance(adapter, GCPAdapter)
        assert adapter.region == "europe-west1"
        assert adapter.environment == "development"

    def test_deployment_version_creation_and_tracking(self):
        """Test deployment version creation and tracking."""
        version = DeploymentVersion(
            version_id="v1.0.0",
            pipeline_id="pipeline-123",
            timestamp=datetime.utcnow(),
            image="myapp:v1.0.0",
            environment="production",
            status="success",
            health_check_passed=True,
            metadata={
                "deployment_id": "myapp-prod",
                "url": "https://myapp.example.com",
                "region": "us-east-1"
            }
        )

        assert version.version_id == "v1.0.0"
        assert version.pipeline_id == "pipeline-123"
        assert version.image == "myapp:v1.0.0"
        assert version.environment == "production"
        assert version.status == "success"
        assert version.health_check_passed is True
        assert version.metadata["deployment_id"] == "myapp-prod"

    def test_deployment_version_rollback_scenario(self):
        """Test deployment version tracking for rollback scenario."""
        # Create deployment versions
        v1 = DeploymentVersion(
            version_id="v1.0.0",
            pipeline_id="pipeline-123",
            image="myapp:v1.0.0",
            environment="production",
            status="success",
            health_check_passed=True,
        )

        v2 = DeploymentVersion(
            version_id="v1.1.0",
            pipeline_id="pipeline-123",
            image="myapp:v1.1.0",
            environment="production",
            status="failed",
            health_check_passed=False,
        )

        # Simulate rollback
        v2.status = "rolled_back"

        assert v1.status == "success"
        assert v2.status == "rolled_back"
        assert v1.image == "myapp:v1.0.0"
        assert v2.image == "myapp:v1.1.0"

    def test_cloud_adapter_deployment_workflow(self):
        """Test complete cloud adapter deployment workflow."""
        with patch("src.executor.cloud_adapters.AWSAdapter._run_command") as mock_run:
            mock_run.return_value = ""
            adapter = AWSAdapter(region="us-east-1", environment="production")

            # Build image
            image_uri = adapter.build_image("Dockerfile", "myapp", "v1.0.0")
            assert "myapp:v1.0.0" in image_uri
            assert "ecr" in image_uri

            # Deploy
            deployment_info = adapter.deploy(image_uri, "myapp", 3000)
            assert deployment_info["status"] == "deployed"
            assert deployment_info["provider"] == "aws"
            assert deployment_info["environment"] == "production"

            # Health check
            with patch("src.executor.cloud_adapters.AWSAdapter._run_command") as mock_health:
                mock_health.return_value = json.dumps({
                    "services": [{"runningCount": 1, "desiredCount": 1}]
                })
                is_healthy = adapter.health_check("myapp")
                assert is_healthy is True

            # Rollback
            with patch("src.executor.cloud_adapters.AWSAdapter._run_command") as mock_rollback:
                mock_rollback.return_value = ""
                success = adapter.rollback("myapp", "myapp:v0.9.0")
                assert success is True

    def test_goal_parsing_with_deployment_strategy(self):
        """Test goal parsing extracts deployment strategy."""
        parser = GoalParser()

        # Blue-green deployment
        result = parser.parse("deploy to AWS with blue-green strategy")
        assert result["strategy"] == "blue_green"
        assert result["cloud"] == "aws"

        # Canary deployment
        result = parser.parse("deploy to Azure with canary strategy")
        assert result["strategy"] == "canary"
        assert result["cloud"] == "azure"

        # Rolling deployment
        result = parser.parse("deploy to GCP with rolling strategy")
        assert result["strategy"] == "rolling"
        assert result["cloud"] == "gcp"

    def test_goal_parsing_validation_and_error_handling(self):
        """Test goal parsing validation and error messages."""
        parser = GoalParser()

        # Invalid: no action
        result = parser.parse("AWS production")
        assert result["is_valid"] is False
        assert "action" in result["error_message"].lower()

        # Invalid: multiple clouds
        result = parser.parse("deploy to AWS and Azure")
        assert result["is_valid"] is False
        assert "multiple clouds" in result["error_message"].lower()

        # Invalid: multiple environments
        result = parser.parse("deploy to production and staging")
        assert result["is_valid"] is False
        assert "multiple environments" in result["error_message"].lower()

        # Valid: complex goal
        result = parser.parse("deploy to AWS us-west-2 production with blue-green strategy")
        assert result["is_valid"] is True
        assert result["error_message"] is None

    def test_cloud_provider_enum(self):
        """Test CloudProvider enum values."""
        assert CloudProvider.AWS.value == "aws"
        assert CloudProvider.AZURE.value == "azure"
        assert CloudProvider.GCP.value == "gcp"
        assert CloudProvider.LOCAL.value == "local"

    def test_multiple_cloud_adapters_independence(self):
        """Test that multiple cloud adapters can be used independently."""
        aws_adapter = get_cloud_adapter("aws", "us-east-1", "production")
        azure_adapter = get_cloud_adapter("azure", "eastus", "staging")
        gcp_adapter = get_cloud_adapter("gcp", "us-central1", "development")

        assert isinstance(aws_adapter, AWSAdapter)
        assert isinstance(azure_adapter, AzureAdapter)
        assert isinstance(gcp_adapter, GCPAdapter)

        assert aws_adapter.region == "us-east-1"
        assert azure_adapter.region == "eastus"
        assert gcp_adapter.region == "us-central1"

        assert aws_adapter.environment == "production"
        assert azure_adapter.environment == "staging"
        assert gcp_adapter.environment == "development"

    def test_deployment_version_metadata_preservation(self):
        """Test that deployment version metadata is preserved."""
        metadata = {
            "deployment_id": "myapp-prod",
            "url": "https://myapp.example.com",
            "region": "us-east-1",
            "strategy": "blue-green",
            "health_check_url": "https://myapp.example.com/health",
            "custom_field": "custom_value"
        }

        version = DeploymentVersion(
            version_id="v1.0.0",
            pipeline_id="pipeline-123",
            image="myapp:v1.0.0",
            environment="production",
            status="success",
            health_check_passed=True,
            metadata=metadata
        )

        # Verify all metadata is preserved
        assert version.metadata == metadata
        assert version.metadata["deployment_id"] == "myapp-prod"
        assert version.metadata["strategy"] == "blue-green"
        assert version.metadata["custom_field"] == "custom_value"

    def test_goal_parser_region_detection_priority(self):
        """Test goal parser region detection priority."""
        parser = GoalParser()

        # AWS region should be detected
        result = parser.parse("deploy to AWS us-west-2")
        assert result["region"] == "us-west-2"

        # Azure region should be detected
        result = parser.parse("deploy to Azure westus")
        assert result["region"] == "westus"

        # GCP region should be detected
        result = parser.parse("deploy to GCP europe-west1")
        assert result["region"] == "europe-west1"

        # Default region if not specified
        result = parser.parse("deploy to AWS")
        assert result["region"] == "us-east-1"

    def test_cloud_adapter_error_handling(self):
        """Test cloud adapter error handling."""
        with patch("src.executor.cloud_adapters.AWSAdapter._run_command") as mock_run:
            mock_run.side_effect = Exception("Command failed")
            adapter = AWSAdapter()

            # Build should raise exception
            with pytest.raises(Exception):
                adapter.build_image("Dockerfile", "myapp", "v1.0.0")

            # Health check should return False on error
            is_healthy = adapter.health_check("myapp")
            assert is_healthy is False

            # Rollback should return False on error
            success = adapter.rollback("myapp", "myapp:v0.9.0")
            assert success is False

    def test_deployment_version_status_transitions(self):
        """Test deployment version status transitions."""
        version = DeploymentVersion(
            version_id="v1.0.0",
            pipeline_id="pipeline-123",
            image="myapp:v1.0.0",
            environment="production",
            status="success",
            health_check_passed=True,
        )

        # Simulate rollback
        assert version.status == "success"
        version.status = "rolled_back"
        assert version.status == "rolled_back"

        # Create failed version
        failed_version = DeploymentVersion(
            version_id="v1.1.0",
            pipeline_id="pipeline-123",
            image="myapp:v1.1.0",
            environment="production",
            status="failed",
            health_check_passed=False,
        )

        assert failed_version.status == "failed"
        assert failed_version.health_check_passed is False

    def test_goal_parser_case_insensitivity(self):
        """Test goal parser is case insensitive."""
        parser = GoalParser()

        result1 = parser.parse("DEPLOY TO AWS PRODUCTION")
        result2 = parser.parse("deploy to aws production")
        result3 = parser.parse("Deploy To AWS Production")

        assert result1["cloud"] == result2["cloud"] == result3["cloud"] == "aws"
        assert result1["environment"] == result2["environment"] == result3["environment"] == "production"

    def test_cloud_adapter_factory_with_defaults(self):
        """Test cloud adapter factory with default parameters."""
        adapter = get_cloud_adapter("aws")
        assert adapter.region == "us-east-1"
        assert adapter.environment == "staging"

        # Azure adapter uses default region from get_cloud_adapter (us-east-1)
        # but the AzureAdapter constructor has its own default (eastus)
        adapter = get_cloud_adapter("azure")
        assert adapter.environment == "staging"

        adapter = get_cloud_adapter("gcp")
        assert adapter.environment == "staging"
