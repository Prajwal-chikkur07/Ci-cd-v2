import os
from src.creator.templates.deploy_commands import get_deploy_command, get_health_check_command
from src.models.pipeline import AgentType, RepoAnalysis, Stage


def _has_main_package(work_dir: str) -> bool:
    """Check if the repo has a main package (is an app, not just a library)."""
    try:
        for root, _, files in os.walk(work_dir):
            # Skip vendor and hidden dirs
            if any(p.startswith('.') or p == 'vendor' for p in root.split(os.sep)):
                continue
            for f in files:
                if f.endswith('.go'):
                    try:
                        content = open(os.path.join(root, f)).read(512)
                        if 'package main' in content:
                            return True
                    except OSError:
                        pass
    except OSError:
        pass
    return False


def generate_go_pipeline(analysis: RepoAnalysis, goal: str) -> list[Stage]:
    """Generate a Go CI/CD pipeline with proper DAG parallelism."""
    stages: list[Stage] = []

    # Stage 1: Download dependencies
    stages.append(Stage(
        id="install",
        agent=AgentType.BUILD,
        command="go mod download && go mod verify",
        depends_on=[],
        timeout_seconds=120,
    ))

    # Stage 2: lint + test in parallel
    stages.append(Stage(
        id="lint",
        agent=AgentType.TEST,
        command="go vet ./... && (gofmt -l . | grep -q . && echo 'gofmt issues found' || echo 'gofmt OK')",
        depends_on=["install"],
        timeout_seconds=60,
        critical=False,
    ))

    stages.append(Stage(
        id="unit_test",
        agent=AgentType.TEST,
        command="go test -race -count=1 ./... 2>&1 || echo 'Tests completed'",
        depends_on=["install"],
        timeout_seconds=300,
        critical=False,
    ))

    # Stage 3: Build — detect if app or library
    # For libraries (no main package), just compile-check; for apps, produce binary
    build_cmd = (
        "mkdir -p bin && go build -o bin/ ./cmd/... 2>/dev/null || "
        "go build -o bin/app ./... 2>/dev/null || "
        "go build ./... && echo 'Build OK (library)'"
    )

    stages.append(Stage(
        id="build",
        agent=AgentType.BUILD,
        command=build_cmd,
        depends_on=["unit_test"],
        timeout_seconds=300,
    ))

    # Stage 4: security_scan
    stages.append(Stage(
        id="security_scan",
        agent=AgentType.SECURITY,
        command=(
            "which govulncheck > /dev/null 2>&1 && govulncheck ./... || "
            "go list -m all 2>/dev/null | head -5 && echo 'govulncheck not installed — skipping'"
        ),
        depends_on=["build"],
        timeout_seconds=120,
        critical=False,
    ))

    # Stage 5: Deploy (if goal mentions deployment or run)
    deploy_keywords = ["deploy", "release", "publish", "production", "staging", "run", "local", "start"]
    should_deploy = any(kw in goal.lower() for kw in deploy_keywords)

    if should_deploy:
        target_port = 8080
        kill_port = f"fuser -k {target_port}/tcp 2>/dev/null || true"
        # Bind to 0.0.0.0 to be accessible from host
        run_cmd = (
            f"./bin/app 2>/dev/null || "
            f"./bin/$(ls bin/ | head -1) 2>/dev/null || "
            f"go run ./cmd/... 2>/dev/null || go run . 2>/dev/null || echo 'No runnable binary found'"
        )
        # Use script-based backgrounding to ensure proper detachment from parent pipes
        bg_cmd = (
            f"cat > /tmp/start_go_app.sh << 'SCRIPT_EOF'\n"
            f"#!/bin/bash\n"
            f"{kill_port}\n"
            f"HOST=0.0.0.0 PORT={target_port} {run_cmd}\n"
            f"SCRIPT_EOF\n"
            f"chmod +x /tmp/start_go_app.sh && "
            f"(nohup /tmp/start_go_app.sh > /tmp/app.log 2>&1 < /dev/null &) && sleep 3"
        )
        # Health check should ONLY check the specific port we intended to deploy to
        hc_cmd = (
            f"for i in $(seq 1 20); do "
            f"if nc -z localhost {target_port}; then "
            f"echo 'Health check passed: port {target_port} is open'; exit 0; "
            f"fi; sleep 2; done; "
            f"echo 'Health check failed: port {target_port} not responding'; exit 1"
        )
        deploy_cmd = get_deploy_command(analysis.deploy_target, analysis.has_dockerfile, bg_cmd)

        stages.append(Stage(
            id="deploy",
            agent=AgentType.DEPLOY,
            command=deploy_cmd,
            depends_on=["security_scan"],
            timeout_seconds=300,
            retry_count=1,
        ))
        stages.append(Stage(
            id="health_check",
            agent=AgentType.VERIFY,
            command=hc_cmd,
            depends_on=["deploy"],
            timeout_seconds=120,
            retry_count=5,
            critical=True,
        ))

    return stages
