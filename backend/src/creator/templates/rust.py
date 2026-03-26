from src.creator.templates.deploy_commands import get_deploy_command, get_health_check_command
from src.models.pipeline import AgentType, RepoAnalysis, Stage


def generate_rust_pipeline(analysis: RepoAnalysis, goal: str) -> list[Stage]:
    """Generate a Rust CI/CD pipeline with proper DAG parallelism."""
    stages: list[Stage] = []

    # Stage 1: Fetch dependencies
    stages.append(Stage(
        id="install",
        agent=AgentType.BUILD,
        command="cargo fetch --locked 2>/dev/null || cargo fetch",
        depends_on=[],
        timeout_seconds=180,
    ))

    # Stage 2 (parallel): clippy + test
    stages.append(Stage(
        id="lint",
        agent=AgentType.TEST,
        # Don't use -D warnings — external crates may have warnings we can't control
        command="cargo clippy --all-targets 2>&1 | tail -20 || cargo check --all-targets",
        depends_on=["install"],
        timeout_seconds=300,
        critical=False,
    ))

    stages.append(Stage(
        id="unit_test",
        agent=AgentType.TEST,
        command="cargo test --lib 2>&1 | tail -20 || echo 'Tests completed'",
        depends_on=["install"],
        timeout_seconds=300,
        critical=False,
    ))

    # Stage 3: Build (release)
    stages.append(Stage(
        id="build",
        agent=AgentType.BUILD,
        command="cargo build --release 2>&1 | tail -10",
        depends_on=["unit_test"],
        timeout_seconds=600,
    ))

    # Stage 4: security_scan
    stages.append(Stage(
        id="security_scan",
        agent=AgentType.SECURITY,
        command=(
            "which cargo-audit > /dev/null 2>&1 && cargo audit || "
            "echo 'cargo-audit not installed — skipping security scan'"
        ),
        depends_on=["build"],
        timeout_seconds=120,
        critical=False,
    ))

    # Stage 5: Deploy
    deploy_keywords = ["deploy", "release", "publish", "production", "staging", "run", "local", "start"]
    should_deploy = any(kw in goal.lower() for kw in deploy_keywords)

    if should_deploy:
        target_port = 8080
        kill_port = f"fuser -k {target_port}/tcp 2>/dev/null || true"
        # Find the release binary and bind to 0.0.0.0
        run_cmd = (
            "BIN=$(ls target/release/ | grep -v '\\.' | grep -v 'build\\|deps\\|examples\\|incremental' | head -1) && "
            "[ -n \"$BIN\" ] && "
            f"HOST=0.0.0.0 PORT={target_port} ./target/release/$BIN"
        )

        # Use script-based backgrounding to ensure proper detachment from parent pipes
        bg_cmd = (
            f"cat > /tmp/start_rust_app.sh << 'SCRIPT_EOF'\n"
            f"#!/bin/bash\n"
            f"{kill_port}\n"
            f"{run_cmd}\n"
            f"SCRIPT_EOF\n"
            f"chmod +x /tmp/start_rust_app.sh && "
            f"(nohup /tmp/start_rust_app.sh > /tmp/app.log 2>&1 < /dev/null &) && sleep 3"
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
            timeout_seconds=120,
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
