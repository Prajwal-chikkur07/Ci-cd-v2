"""Unit tests for GoalParser."""
from __future__ import annotations

import pytest

from src.creator.goal_parser import GoalParser


@pytest.fixture
def parser():
    return GoalParser()


def test_parse_returns_dict(parser):
    result = parser.parse("deploy to AWS ECS in us-east-1")
    assert isinstance(result, dict)


def test_parse_detects_aws(parser):
    result = parser.parse("deploy to AWS ECS production")
    cloud = result.get("cloud", "").lower()
    assert "aws" in cloud or cloud == "aws"


def test_parse_detects_gcp(parser):
    result = parser.parse("deploy to Google Cloud Run staging")
    cloud = result.get("cloud", "").lower()
    assert "gcp" in cloud or "google" in cloud or cloud == "gcp"


def test_parse_detects_azure(parser):
    result = parser.parse("deploy to Azure App Service")
    cloud = result.get("cloud", "").lower()
    assert "azure" in cloud


def test_parse_detects_environment_production(parser):
    result = parser.parse("deploy to production on AWS")
    env = result.get("environment", "").lower()
    assert "prod" in env


def test_parse_detects_environment_staging(parser):
    result = parser.parse("deploy to staging environment")
    env = result.get("environment", "").lower()
    assert "stag" in env


def test_parse_detects_region(parser):
    result = parser.parse("deploy to AWS us-east-1")
    region = result.get("region", "")
    assert "us-east-1" in region or "us" in region.lower()


def test_parse_local_goal(parser):
    result = parser.parse("run locally for development")
    cloud = result.get("cloud", "").lower()
    assert cloud in ("local", "", "none") or "local" in cloud


def test_parse_empty_goal_returns_dict(parser):
    result = parser.parse("")
    assert isinstance(result, dict)


def test_parse_docker_goal(parser):
    result = parser.parse("build and push Docker image to registry")
    assert isinstance(result, dict)
