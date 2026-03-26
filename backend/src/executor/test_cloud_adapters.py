"""Unit tests for cloud adapters."""

import json
import os
from unittest.mock import patch

import pytest

from src.executor.cloud_adapters import (
    AWSAdapter,
    AzureAdapter,
    CloudProvider,
    GCPAdapter,
    get_cloud_adapter,
)


class TestCloudProvider:
    """Test CloudProvider enum."""

    def test_cloud_provider_values(self):
        """Test CloudProvider enum values."""
        assert CloudProvider.AWS.value == "aws"
        assert CloudProvider.AZURE.value == "azure"
        assert CloudProvider.GCP.value == "gcp"
        assert CloudProvider.LOCAL.value == "local"


class TestAWSAdapter:
    """Test AWS adapter."""

    def test_init_default(self):
        """Test AWS adapter initialization with defaults."""
        adapter = AWSAdapter()
        assert adapter.region == "us-east-1"
        assert adapter.environment == "staging"
        assert adapter.account_id == "123456789012"

    def test_init_custom(self):
        """Test AWS adapter initialization with custom values."""
        adapter = AWSAdapter(region="us-west-2", environment="production")
        assert adapter.region == "us-west-2"
        assert adapter.environment == "production"

    @patch.dict(os.environ, {"AWS_ACCOUNT_ID": "999888777666"})
    def test_init_with_env_account_id(self):
        """Test AWS adapter uses AWS_ACCOUNT_ID from environment."""
        adapter = AWSAdapter()
        assert adapter.account_id == "999888777666"

    @patch("src.executor.cloud_adapters.AWSAdapter._run_command")
    def test_build_image_success(self, mock_run):
        """Test successful image build and push to ECR."""
        mock_run.return_value = ""
        adapter = AWSAdapter(region="us-east-1")

        result = adapter.build_image("Dockerfile", "myapp", "v1.0")

        assert result == "123456789012.dkr.ecr.us-east-1.amazonaws.com/myapp:v1.0"
        assert mock_run.call_count == 4  # login, build, tag, push

    @patch("src.executor.cloud_adapters.AWSAdapter._run_command")
    def test_build_image_failure(self, mock_run):
        """Test image build failure."""
        mock_run.side_effect = Exception("Build failed")
        adapter = AWSAdapter()

        with pytest.raises(Exception):
            adapter.build_image("Dockerfile", "myapp", "v1.0")

    @patch("src.executor.cloud_adapters.AWSAdapter._run_command")
    def test_deploy_success(self, mock_run):
        """Test successful deployment to ECS."""
        mock_run.return_value = ""
        adapter = AWSAdapter(region="us-east-1")

        result = adapter.deploy(
            "123456789012.dkr.ecr.us-east-1.amazonaws.com/myapp:v1.0",
            "myapp",
            3000
        )

        assert result["status"] == "deployed"
        assert result["deployment_id"] == "myapp"
        assert result["provider"] == "aws"
        assert "url" in result

    @patch("src.executor.cloud_adapters.AWSAdapter._run_command")
    def test_health_check_healthy(self, mock_run):
        """Test health check for healthy service."""
        service_data = {
            "services": [
                {
                    "runningCount": 1,
                    "desiredCount": 1
                }
            ]
        }
        mock_run.return_value = json.dumps(service_data)
        adapter = AWSAdapter()

        result = adapter.health_check("myapp")

        assert result is True

    @patch("src.executor.cloud_adapters.AWSAdapter._run_command")
    def test_health_check_unhealthy(self, mock_run):
        """Test health check for unhealthy service."""
        service_data = {
            "services": [
                {
                    "runningCount": 0,
                    "desiredCount": 1
                }
            ]
        }
        mock_run.return_value = json.dumps(service_data)
        adapter = AWSAdapter()

        result = adapter.health_check("myapp")

        assert result is False

    @patch("src.executor.cloud_adapters.AWSAdapter._run_command")
    def test_health_check_no_services(self, mock_run):
        """Test health check when no services found."""
        mock_run.return_value = json.dumps({"services": []})
        adapter = AWSAdapter()

        result = adapter.health_check("myapp")

        assert result is False

    @patch("src.executor.cloud_adapters.AWSAdapter._run_command")
    def test_rollback_success(self, mock_run):
        """Test successful rollback."""
        mock_run.return_value = ""
        adapter = AWSAdapter()

        result = adapter.rollback("myapp", "myapp:1")

        assert result is True
        mock_run.assert_called_once()

    @patch("src.executor.cloud_adapters.AWSAdapter._run_command")
    def test_rollback_failure(self, mock_run):
        """Test rollback failure."""
        mock_run.side_effect = Exception("Rollback failed")
        adapter = AWSAdapter()

        result = adapter.rollback("myapp", "myapp:1")

        assert result is False


class TestAzureAdapter:
    """Test Azure adapter."""

    def test_init_default(self):
        """Test Azure adapter initialization with defaults."""
        adapter = AzureAdapter()
        assert adapter.region == "eastus"
        assert adapter.environment == "staging"
        assert adapter.resource_group == "default-rg"
        assert adapter.registry_name == "myregistry"

    def test_init_custom(self):
        """Test Azure adapter initialization with custom values."""
        adapter = AzureAdapter(region="westus", environment="production")
        assert adapter.region == "westus"
        assert adapter.environment == "production"

    @patch.dict(os.environ, {
        "AZURE_RESOURCE_GROUP": "prod-rg",
        "AZURE_REGISTRY_NAME": "prodregistry"
    })
    def test_init_with_env_vars(self):
        """Test Azure adapter uses environment variables."""
        adapter = AzureAdapter()
        assert adapter.resource_group == "prod-rg"
        assert adapter.registry_name == "prodregistry"

    @patch("src.executor.cloud_adapters.AzureAdapter._run_command")
    def test_build_image_success(self, mock_run):
        """Test successful image build and push to ACR."""
        mock_run.return_value = ""
        adapter = AzureAdapter()

        result = adapter.build_image("Dockerfile", "myapp", "v1.0")

        assert result == "myregistry.azurecr.io/myapp:v1.0"
        assert mock_run.call_count == 2  # login, build

    @patch("src.executor.cloud_adapters.AzureAdapter._run_command")
    def test_deploy_success(self, mock_run):
        """Test successful deployment to ACI."""
        mock_run.side_effect = ["", "myapp.eastus.azurecontainer.io"]
        adapter = AzureAdapter()

        result = adapter.deploy(
            "myregistry.azurecr.io/myapp:v1.0",
            "myapp",
            3000
        )

        assert result["status"] == "deployed"
        assert result["deployment_id"] == "myapp"
        assert result["provider"] == "azure"
        assert "url" in result

    @patch("src.executor.cloud_adapters.AzureAdapter._run_command")
    def test_health_check_running(self, mock_run):
        """Test health check for running container."""
        mock_run.return_value = "Running"
        adapter = AzureAdapter()

        result = adapter.health_check("myapp")

        assert result is True

    @patch("src.executor.cloud_adapters.AzureAdapter._run_command")
    def test_health_check_not_running(self, mock_run):
        """Test health check for stopped container."""
        mock_run.return_value = "Stopped"
        adapter = AzureAdapter()

        result = adapter.health_check("myapp")

        assert result is False

    @patch("src.executor.cloud_adapters.AzureAdapter._run_command")
    def test_rollback_success(self, mock_run):
        """Test successful rollback."""
        mock_run.return_value = ""
        adapter = AzureAdapter()

        result = adapter.rollback("myapp", "myregistry.azurecr.io/myapp:v0.9")

        assert result is True
        assert mock_run.call_count == 2  # delete, create

    @patch("src.executor.cloud_adapters.AzureAdapter._run_command")
    def test_rollback_failure(self, mock_run):
        """Test rollback failure."""
        mock_run.side_effect = Exception("Rollback failed")
        adapter = AzureAdapter()

        result = adapter.rollback("myapp", "myregistry.azurecr.io/myapp:v0.9")

        assert result is False


class TestGCPAdapter:
    """Test GCP adapter."""

    def test_init_default(self):
        """Test GCP adapter initialization with defaults."""
        adapter = GCPAdapter()
        assert adapter.region == "us-central1"
        assert adapter.environment == "staging"
        assert adapter.project_id == "my-project"

    def test_init_custom(self):
        """Test GCP adapter initialization with custom values."""
        adapter = GCPAdapter(region="europe-west1", environment="production")
        assert adapter.region == "europe-west1"
        assert adapter.environment == "production"

    @patch.dict(os.environ, {"GCP_PROJECT_ID": "prod-project"})
    def test_init_with_env_project_id(self):
        """Test GCP adapter uses GCP_PROJECT_ID from environment."""
        adapter = GCPAdapter()
        assert adapter.project_id == "prod-project"

    @patch("src.executor.cloud_adapters.GCPAdapter._run_command")
    def test_build_image_success(self, mock_run):
        """Test successful image build and push to GCR."""
        mock_run.return_value = ""
        adapter = GCPAdapter()

        result = adapter.build_image("Dockerfile", "myapp", "v1.0")

        assert result == "gcr.io/my-project/myapp:v1.0"
        mock_run.assert_called_once()

    @patch("src.executor.cloud_adapters.GCPAdapter._run_command")
    def test_deploy_success(self, mock_run):
        """Test successful deployment to Cloud Run."""
        mock_run.side_effect = ["", "https://myapp-abc123.run.app"]
        adapter = GCPAdapter()

        result = adapter.deploy(
            "gcr.io/my-project/myapp:v1.0",
            "myapp",
            3000
        )

        assert result["status"] == "deployed"
        assert result["deployment_id"] == "myapp"
        assert result["provider"] == "gcp"
        assert result["url"] == "https://myapp-abc123.run.app"

    @patch("src.executor.cloud_adapters.GCPAdapter._run_command")
    def test_health_check_healthy(self, mock_run):
        """Test health check for healthy service."""
        mock_run.return_value = "True"
        adapter = GCPAdapter()

        result = adapter.health_check("myapp")

        assert result is True

    @patch("src.executor.cloud_adapters.GCPAdapter._run_command")
    def test_health_check_unhealthy(self, mock_run):
        """Test health check for unhealthy service."""
        mock_run.return_value = "False"
        adapter = GCPAdapter()

        result = adapter.health_check("myapp")

        assert result is False

    @patch("src.executor.cloud_adapters.GCPAdapter._run_command")
    def test_rollback_success(self, mock_run):
        """Test successful rollback."""
        mock_run.return_value = ""
        adapter = GCPAdapter()

        result = adapter.rollback("myapp", "myapp-v1")

        assert result is True
        mock_run.assert_called_once()

    @patch("src.executor.cloud_adapters.GCPAdapter._run_command")
    def test_rollback_failure(self, mock_run):
        """Test rollback failure."""
        mock_run.side_effect = Exception("Rollback failed")
        adapter = GCPAdapter()

        result = adapter.rollback("myapp", "myapp-v1")

        assert result is False


class TestGetCloudAdapter:
    """Test cloud adapter factory function."""

    def test_get_aws_adapter(self):
        """Test getting AWS adapter."""
        adapter = get_cloud_adapter("aws", "us-west-2", "production")
        assert isinstance(adapter, AWSAdapter)
        assert adapter.region == "us-west-2"
        assert adapter.environment == "production"

    def test_get_azure_adapter(self):
        """Test getting Azure adapter."""
        adapter = get_cloud_adapter("azure", "westus", "staging")
        assert isinstance(adapter, AzureAdapter)
        assert adapter.region == "westus"
        assert adapter.environment == "staging"

    def test_get_gcp_adapter(self):
        """Test getting GCP adapter."""
        adapter = get_cloud_adapter("gcp", "europe-west1", "dev")
        assert isinstance(adapter, GCPAdapter)
        assert adapter.region == "europe-west1"
        assert adapter.environment == "dev"

    def test_get_adapter_case_insensitive(self):
        """Test adapter factory is case insensitive."""
        adapter1 = get_cloud_adapter("AWS")
        adapter2 = get_cloud_adapter("aws")
        assert isinstance(adapter1, AWSAdapter)
        assert isinstance(adapter2, AWSAdapter)

    def test_get_adapter_invalid_provider(self):
        """Test error for invalid provider."""
        with pytest.raises(ValueError):
            get_cloud_adapter("invalid")

    def test_get_adapter_default_region_environment(self):
        """Test default region and environment."""
        adapter = get_cloud_adapter("aws")
        assert adapter.region == "us-east-1"
        assert adapter.environment == "staging"
