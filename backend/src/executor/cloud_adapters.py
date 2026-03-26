"""Cloud deployment adapters for AWS, Azure, and GCP."""

import json
import logging
import os
import subprocess
from abc import ABC, abstractmethod
from enum import Enum
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


class CloudProvider(Enum):
    """Supported cloud providers."""
    AWS = "aws"
    AZURE = "azure"
    GCP = "gcp"
    LOCAL = "local"


class CloudAdapter(ABC):
    """Abstract base class for cloud deployment adapters."""

    def __init__(self, region: str = "us-east-1", environment: str = "staging"):
        """Initialize cloud adapter.
        
        Args:
            region: Cloud region for deployment
            environment: Deployment environment (staging, production, dev)
        """
        self.region = region
        self.environment = environment
        self.logger = logger

    @abstractmethod
    def build_image(self, dockerfile_path: str, image_name: str, tag: str = "latest") -> str:
        """Build and push image to cloud registry.
        
        Args:
            dockerfile_path: Path to Dockerfile
            image_name: Name for the image
            tag: Image tag (default: latest)
            
        Returns:
            Full image URI in cloud registry
            
        Raises:
            Exception: If build or push fails
        """
        pass

    @abstractmethod
    def deploy(self, image: str, app_name: str, port: int = 3000) -> Dict[str, Any]:
        """Deploy image to cloud.
        
        Args:
            image: Full image URI from registry
            app_name: Name for the deployed application
            port: Port to expose (default: 3000)
            
        Returns:
            Deployment info: {url, status, deployment_id, ...}
            
        Raises:
            Exception: If deployment fails
        """
        pass

    @abstractmethod
    def health_check(self, deployment_id: str) -> bool:
        """Check if deployment is healthy.
        
        Args:
            deployment_id: ID of the deployment to check
            
        Returns:
            True if healthy, False otherwise
        """
        pass

    @abstractmethod
    def rollback(self, deployment_id: str, previous_version: str) -> bool:
        """Rollback to previous version.
        
        Args:
            deployment_id: ID of the deployment to rollback
            previous_version: Version to rollback to
            
        Returns:
            True if rollback succeeded, False otherwise
        """
        pass

    def _run_command(self, command: str, check: bool = True) -> str:
        """Run shell command and return output.
        
        Args:
            command: Command to run
            check: Raise exception if command fails
            
        Returns:
            Command output
            
        Raises:
            subprocess.CalledProcessError: If command fails and check=True
        """
        try:
            result = subprocess.run(
                command,
                shell=True,
                capture_output=True,
                text=True,
                check=check
            )
            return result.stdout.strip()
        except subprocess.CalledProcessError as e:
            self.logger.error(f"Command failed: {command}\nStderr: {e.stderr}")
            raise


class AWSAdapter(CloudAdapter):
    """AWS deployment adapter (ECR, ECS, Lambda)."""

    def __init__(self, region: str = "us-east-1", environment: str = "staging"):
        """Initialize AWS adapter.
        
        Args:
            region: AWS region
            environment: Deployment environment
        """
        super().__init__(region, environment)
        self.account_id = os.getenv("AWS_ACCOUNT_ID", "123456789012")
        self.registry_url = f"{self.account_id}.dkr.ecr.{region}.amazonaws.com"

    def build_image(self, dockerfile_path: str, image_name: str, tag: str = "latest") -> str:
        """Build and push image to ECR.
        
        Args:
            dockerfile_path: Path to Dockerfile
            image_name: Name for the image
            tag: Image tag
            
        Returns:
            Full ECR image URI
        """
        try:
            # Login to ECR
            login_cmd = (
                f"aws ecr get-login-password --region {self.region} | "
                f"docker login --username AWS --password-stdin {self.registry_url}"
            )
            self._run_command(login_cmd)
            self.logger.info(f"Logged in to ECR: {self.registry_url}")

            # Build image
            build_cmd = f"docker build -t {image_name}:{tag} -f {dockerfile_path} ."
            self._run_command(build_cmd)
            self.logger.info(f"Built image: {image_name}:{tag}")

            # Tag for ECR
            ecr_image = f"{self.registry_url}/{image_name}:{tag}"
            tag_cmd = f"docker tag {image_name}:{tag} {ecr_image}"
            self._run_command(tag_cmd)
            self.logger.info(f"Tagged image for ECR: {ecr_image}")

            # Push to ECR
            push_cmd = f"docker push {ecr_image}"
            self._run_command(push_cmd)
            self.logger.info(f"Pushed image to ECR: {ecr_image}")

            return ecr_image
        except Exception as e:
            self.logger.error(f"Failed to build/push image to ECR: {e}")
            raise

    def deploy(self, image: str, app_name: str, port: int = 3000) -> Dict[str, Any]:
        """Deploy image to ECS.
        
        Args:
            image: ECR image URI
            app_name: Application name
            port: Port to expose
            
        Returns:
            Deployment info
        """
        try:
            # Create ECS task definition
            task_def = {
                "family": app_name,
                "networkMode": "awsvpc",
                "requiresCompatibilities": ["FARGATE"],
                "cpu": "256",
                "memory": "512",
                "containerDefinitions": [
                    {
                        "name": app_name,
                        "image": image,
                        "portMappings": [
                            {
                                "containerPort": port,
                                "hostPort": port,
                                "protocol": "tcp"
                            }
                        ],
                        "logConfiguration": {
                            "logDriver": "awslogs",
                            "options": {
                                "awslogs-group": f"/ecs/{app_name}",
                                "awslogs-region": self.region,
                                "awslogs-stream-prefix": "ecs"
                            }
                        }
                    }
                ]
            }

            # Register task definition
            task_def_json = json.dumps(task_def)
            register_cmd = (
                f"aws ecs register-task-definition --region {self.region} "
                f"--cli-input-json '{task_def_json}'"
            )
            output = self._run_command(register_cmd)
            self.logger.info(f"Registered ECS task definition: {app_name}")

            # Create ECS service (simplified - assumes cluster exists)
            service_cmd = (
                f"aws ecs create-service --region {self.region} "
                f"--cluster default --service-name {app_name} "
                f"--task-definition {app_name} --desired-count 1 "
                f"--launch-type FARGATE"
            )
            output = self._run_command(service_cmd, check=False)
            self.logger.info(f"Created ECS service: {app_name}")

            # Return deployment info
            return {
                "status": "deployed",
                "deployment_id": app_name,
                "url": f"http://{app_name}.{self.region}.elb.amazonaws.com:{port}",
                "provider": "aws",
                "image": image,
                "environment": self.environment
            }
        except Exception as e:
            self.logger.error(f"Failed to deploy to ECS: {e}")
            raise

    def health_check(self, deployment_id: str) -> bool:
        """Check ECS service health.
        
        Args:
            deployment_id: ECS service name
            
        Returns:
            True if service is running and healthy
        """
        try:
            cmd = (
                f"aws ecs describe-services --region {self.region} "
                f"--cluster default --services {deployment_id}"
            )
            output = self._run_command(cmd)
            data = json.loads(output)
            
            if not data.get("services"):
                return False
            
            service = data["services"][0]
            running_count = service.get("runningCount", 0)
            desired_count = service.get("desiredCount", 0)
            
            return running_count > 0 and running_count == desired_count
        except Exception as e:
            self.logger.error(f"Health check failed for {deployment_id}: {e}")
            return False

    def rollback(self, deployment_id: str, previous_version: str) -> bool:
        """Rollback ECS service to previous task definition.
        
        Args:
            deployment_id: ECS service name
            previous_version: Previous task definition ARN or version
            
        Returns:
            True if rollback succeeded
        """
        try:
            cmd = (
                f"aws ecs update-service --region {self.region} "
                f"--cluster default --service {deployment_id} "
                f"--task-definition {previous_version}"
            )
            self._run_command(cmd)
            self.logger.info(f"Rolled back {deployment_id} to {previous_version}")
            return True
        except Exception as e:
            self.logger.error(f"Rollback failed for {deployment_id}: {e}")
            return False


class AzureAdapter(CloudAdapter):
    """Azure deployment adapter (ACR, ACI, App Service)."""

    def __init__(self, region: str = "eastus", environment: str = "staging"):
        """Initialize Azure adapter.
        
        Args:
            region: Azure region
            environment: Deployment environment
        """
        super().__init__(region, environment)
        self.resource_group = os.getenv("AZURE_RESOURCE_GROUP", "default-rg")
        self.registry_name = os.getenv("AZURE_REGISTRY_NAME", "myregistry")
        self.registry_url = f"{self.registry_name}.azurecr.io"

    def build_image(self, dockerfile_path: str, image_name: str, tag: str = "latest") -> str:
        """Build and push image to ACR.
        
        Args:
            dockerfile_path: Path to Dockerfile
            image_name: Name for the image
            tag: Image tag
            
        Returns:
            Full ACR image URI
        """
        try:
            # Login to ACR
            login_cmd = (
                f"az acr login --name {self.registry_name}"
            )
            self._run_command(login_cmd)
            self.logger.info(f"Logged in to ACR: {self.registry_url}")

            # Build image using ACR
            build_cmd = (
                f"az acr build --registry {self.registry_name} "
                f"--image {image_name}:{tag} "
                f"-f {dockerfile_path} ."
            )
            self._run_command(build_cmd)
            self.logger.info(f"Built image in ACR: {image_name}:{tag}")

            acr_image = f"{self.registry_url}/{image_name}:{tag}"
            return acr_image
        except Exception as e:
            self.logger.error(f"Failed to build/push image to ACR: {e}")
            raise

    def deploy(self, image: str, app_name: str, port: int = 3000) -> Dict[str, Any]:
        """Deploy image to ACI or App Service.
        
        Args:
            image: ACR image URI
            app_name: Application name
            port: Port to expose
            
        Returns:
            Deployment info
        """
        try:
            # Deploy to ACI
            deploy_cmd = (
                f"az container create --resource-group {self.resource_group} "
                f"--name {app_name} --image {image} "
                f"--ports {port} --cpu 1 --memory 1 "
                f"--registry-login-server {self.registry_url}"
            )
            output = self._run_command(deploy_cmd)
            self.logger.info(f"Deployed to ACI: {app_name}")

            # Get container info
            info_cmd = (
                f"az container show --resource-group {self.resource_group} "
                f"--name {app_name} --query ipAddress.fqdn"
            )
            fqdn = self._run_command(info_cmd).strip('"')
            self.logger.info(f"Container FQDN: {fqdn}")

            return {
                "status": "deployed",
                "deployment_id": app_name,
                "url": f"http://{fqdn}:{port}",
                "provider": "azure",
                "image": image,
                "environment": self.environment
            }
        except Exception as e:
            self.logger.error(f"Failed to deploy to ACI: {e}")
            raise

    def health_check(self, deployment_id: str) -> bool:
        """Check ACI container health.
        
        Args:
            deployment_id: Container name
            
        Returns:
            True if container is running
        """
        try:
            cmd = (
                f"az container show --resource-group {self.resource_group} "
                f"--name {deployment_id} --query instanceView.state"
            )
            output = self._run_command(cmd).strip('"')
            return output.lower() == "running"
        except Exception as e:
            self.logger.error(f"Health check failed for {deployment_id}: {e}")
            return False

    def rollback(self, deployment_id: str, previous_version: str) -> bool:
        """Rollback ACI container to previous image.
        
        Args:
            deployment_id: Container name
            previous_version: Previous image URI
            
        Returns:
            True if rollback succeeded
        """
        try:
            # Delete current container
            delete_cmd = (
                f"az container delete --resource-group {self.resource_group} "
                f"--name {deployment_id} --yes"
            )
            self._run_command(delete_cmd)
            self.logger.info(f"Deleted container: {deployment_id}")

            # Redeploy with previous image
            deploy_cmd = (
                f"az container create --resource-group {self.resource_group} "
                f"--name {deployment_id} --image {previous_version} "
                f"--ports 3000 --cpu 1 --memory 1"
            )
            self._run_command(deploy_cmd)
            self.logger.info(f"Rolled back {deployment_id} to {previous_version}")
            return True
        except Exception as e:
            self.logger.error(f"Rollback failed for {deployment_id}: {e}")
            return False


class GCPAdapter(CloudAdapter):
    """GCP deployment adapter (GCR, Cloud Run, GKE)."""

    def __init__(self, region: str = "us-central1", environment: str = "staging"):
        """Initialize GCP adapter.
        
        Args:
            region: GCP region
            environment: Deployment environment
        """
        super().__init__(region, environment)
        self.project_id = os.getenv("GCP_PROJECT_ID", "my-project")
        self.registry_url = f"gcr.io/{self.project_id}"

    def build_image(self, dockerfile_path: str, image_name: str, tag: str = "latest") -> str:
        """Build and push image to GCR.
        
        Args:
            dockerfile_path: Path to Dockerfile
            image_name: Name for the image
            tag: Image tag
            
        Returns:
            Full GCR image URI
        """
        try:
            # Build image using Cloud Build
            build_cmd = (
                f"gcloud builds submit --project {self.project_id} "
                f"--tag {self.registry_url}/{image_name}:{tag} "
                f"-f {dockerfile_path} ."
            )
            self._run_command(build_cmd)
            self.logger.info(f"Built image in GCR: {image_name}:{tag}")

            gcr_image = f"{self.registry_url}/{image_name}:{tag}"
            return gcr_image
        except Exception as e:
            self.logger.error(f"Failed to build/push image to GCR: {e}")
            raise

    def deploy(self, image: str, app_name: str, port: int = 3000) -> Dict[str, Any]:
        """Deploy image to Cloud Run.
        
        Args:
            image: GCR image URI
            app_name: Application name
            port: Port to expose
            
        Returns:
            Deployment info
        """
        try:
            # Deploy to Cloud Run
            deploy_cmd = (
                f"gcloud run deploy {app_name} --project {self.project_id} "
                f"--image {image} --region {self.region} "
                f"--port {port} --allow-unauthenticated"
            )
            output = self._run_command(deploy_cmd)
            self.logger.info(f"Deployed to Cloud Run: {app_name}")

            # Get service URL
            url_cmd = (
                f"gcloud run services describe {app_name} --project {self.project_id} "
                f"--region {self.region} --format='value(status.url)'"
            )
            url = self._run_command(url_cmd).strip()
            self.logger.info(f"Cloud Run URL: {url}")

            return {
                "status": "deployed",
                "deployment_id": app_name,
                "url": url,
                "provider": "gcp",
                "image": image,
                "environment": self.environment
            }
        except Exception as e:
            self.logger.error(f"Failed to deploy to Cloud Run: {e}")
            raise

    def health_check(self, deployment_id: str) -> bool:
        """Check Cloud Run service health.
        
        Args:
            deployment_id: Cloud Run service name
            
        Returns:
            True if service is running
        """
        try:
            cmd = (
                f"gcloud run services describe {deployment_id} "
                f"--project {self.project_id} --region {self.region} "
                f"--format='value(status.conditions[0].status)'"
            )
            output = self._run_command(cmd).strip()
            return output.lower() == "true"
        except Exception as e:
            self.logger.error(f"Health check failed for {deployment_id}: {e}")
            return False

    def rollback(self, deployment_id: str, previous_version: str) -> bool:
        """Rollback Cloud Run service to previous revision.
        
        Args:
            deployment_id: Cloud Run service name
            previous_version: Previous revision name
            
        Returns:
            True if rollback succeeded
        """
        try:
            cmd = (
                f"gcloud run services update-traffic {deployment_id} "
                f"--project {self.project_id} --region {self.region} "
                f"--to-revisions {previous_version}=100"
            )
            self._run_command(cmd)
            self.logger.info(f"Rolled back {deployment_id} to {previous_version}")
            return True
        except Exception as e:
            self.logger.error(f"Rollback failed for {deployment_id}: {e}")
            return False


def get_cloud_adapter(provider: str, region: str = "us-east-1", environment: str = "staging") -> CloudAdapter:
    """Factory function to get appropriate cloud adapter.
    
    Args:
        provider: Cloud provider name (aws, azure, gcp, local)
        region: Cloud region
        environment: Deployment environment
        
    Returns:
        CloudAdapter instance
        
    Raises:
        ValueError: If provider is not supported
    """
    provider_lower = provider.lower()
    
    if provider_lower == "aws":
        return AWSAdapter(region, environment)
    elif provider_lower == "azure":
        return AzureAdapter(region, environment)
    elif provider_lower == "gcp":
        return GCPAdapter(region, environment)
    else:
        raise ValueError(f"Unsupported cloud provider: {provider}")
