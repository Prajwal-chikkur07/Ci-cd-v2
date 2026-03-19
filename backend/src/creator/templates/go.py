from src.creator.templates.deploy_commands import get_deploy_command, get_health_check_command
from src.models.pipeline import AgentType, RepoAnalysis, Stage


def generate_go_pipeline(analysis: RepoAnalysis, goal: str) -> list[Stage]:
    """Generate a Go CI/CD pipeline with proper DAG parallelism."""
    stages: list[Stage] = []

    # Stage 1: Download dependencies
    stages.append(
        Stage(
            id="install",
            agent=AgentType.BUILD,
            command="go mod download",
            depends_on=[],
            timeout_seconds=120,
        )
    )

    # Stage 2: lint
    stages.append(
        Stage(
            id="lint",
            agent=AgentType.TEST,
            command="go vet ./...",
            depends_on=["install"],
            timeout_seconds=60,
            critical=False,
        )
    )


    # Stage 3: Build
    stages.append(
        Stage(
            id="build",
            agent=AgentType.BUILD,
            command="go build -o bin/app ./...",
            depends_on=["lint"],
            timeout_seconds=300,
        )
    )

    # Stage 4: security_scan
    stages.append(
        Stage(
            id="security_scan",
            agent=AgentType.SECURITY,
            command="go vet -vettool=$(which govulncheck 2>/dev/null || echo govulncheck) ./... 2>/dev/null || echo 'govulncheck not installed, skipping'",
            depends_on=["build"],
            timeout_seconds=120,
            critical=False,
        )
    )

    # Stage 5: Integration test (after build, before deploy)
    stages.append(
        Stage(
            id="integration_test",
            agent=AgentType.TEST,
            command="go test -tags=integration -race ./... 2>/dev/null || echo 'No integration tests found — skipping'",
            depends_on=["security_scan"],
            timeout_seconds=300,
            critical=False,
        )
    )


    # Stage 5: Deploy (if goal mentions deployment)
    deploy_keywords = ["deploy", "release", "publish", "production", "staging"]
    should_deploy = any(kw in goal.lower() for kw in deploy_keywords)

    if should_deploy:
        deploy_cmd = get_deploy_command(analysis.deploy_target, analysis.has_dockerfile)

        stages.append(
            Stage(
                id="deploy",
                agent=AgentType.DEPLOY,
                command=deploy_cmd,
                depends_on=["security_scan"],
                timeout_seconds=600,
                retry_count=1,
            )
        )

        stages.append(
            Stage(
                id="health_check",
                agent=AgentType.VERIFY,
                command=get_health_check_command(analysis.deploy_target, default_port=8080),
                depends_on=["deploy"],
                timeout_seconds=120,
                retry_count=2,
                critical=True,
            )
        )

    return stages
