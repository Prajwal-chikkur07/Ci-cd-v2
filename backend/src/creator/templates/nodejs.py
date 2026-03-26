from src.creator.templates.deploy_commands import get_deploy_command, get_health_check_command
from src.models.pipeline import AgentType, RepoAnalysis, Stage


def generate_nodejs_pipeline(analysis: RepoAnalysis, goal: str) -> list[Stage]:
    """Generate a Node.js CI/CD pipeline with proper DAG parallelism."""
    use_yarn = analysis.has_yarn_lock or analysis.package_manager == "yarn"
    use_pnpm = analysis.package_manager == "pnpm"
    scripts = analysis.available_scripts

    # Prefix all commands with subdir cd if project is in a subdirectory
    subdir = analysis.project_subdir
    prefix = f"cd {subdir} && " if subdir else ""

    if use_yarn:
        run = "yarn"
        install_cmd = f"{prefix}yarn install --frozen-lockfile"
        audit_cmd = f"{prefix}yarn audit --level moderate || true"
    elif use_pnpm:
        run = "pnpm"
        install_cmd = f"{prefix}pnpm install --frozen-lockfile"
        audit_cmd = f"{prefix}pnpm audit --audit-level moderate || true"
    else:
        run = "npm"
        install_cmd = f"{prefix}npm install"
        audit_cmd = f"{prefix}npm audit --audit-level=moderate || true"

    stages: list[Stage] = []

    # Stage 1: Install dependencies
    stages.append(
        Stage(
            id="install",
            agent=AgentType.BUILD,
            command=install_cmd,
            depends_on=[],
            timeout_seconds=120,
        )
    )

    # Stage 2 (parallel): lint, unit_test
    has_lint = "lint" in scripts
    has_test = "test" in scripts
    has_build = "build" in scripts

    if has_lint:
        lint_cmd = f"{prefix}{run} run lint"
    else:
        lint_cmd = "echo 'No lint script found, skipping'"

    stages.append(
        Stage(
            id="lint",
            agent=AgentType.TEST,
            command=lint_cmd,
            depends_on=["install"],
            timeout_seconds=60,
            critical=False,
        )
    )

    if has_test:
        # Detect test runner to add CI/non-watch flags
        test_runner = analysis.test_runner or ""
        if test_runner == "vitest":
            test_cmd = f"{prefix}{run} run vitest run"
        elif analysis.framework in ("react", "nextjs") or "react-scripts" in " ".join(scripts):
            test_cmd = f"{prefix}CI=true {run} test"
        else:
            test_cmd = f"{prefix}CI=true {run} test -- --watchAll=false 2>/dev/null || {prefix}CI=true {run} test"
        stages.append(
            Stage(
                id="unit_test",
                agent=AgentType.TEST,
                command=test_cmd,
                depends_on=["install"],
                timeout_seconds=120,
                critical=False,  # Don't block pipeline if tests fail
            )
        )

    # Stage 3: Build
    if has_build:
        build_cmd = f"{prefix}{run} run build"
    else:
        build_cmd = "echo 'No build script found — install verified, package is ready'"

    # Next.js builds are heavier — give them more time and a retry
    is_nextjs = analysis.framework in ("nextjs", "next")
    build_deps = []
    if has_lint:
        build_deps.append("lint")
    if has_test:
        build_deps.append("unit_test")

    stages.append(
        Stage(
            id="build",
            agent=AgentType.BUILD,
            command=build_cmd,
            depends_on=build_deps,
            timeout_seconds=600 if is_nextjs else 300,
            retry_count=1 if is_nextjs else 0,
            critical=True,
        )
    )

    # Stage 4: security_scan (Only add once)
    stages.append(
        Stage(
            id="security_scan",
            agent=AgentType.SECURITY,
            command=audit_cmd,
            depends_on=["build"],
            timeout_seconds=120,
            critical=False,
        )
    )

    # Stage 5: Integration test (after build, before deploy)
    has_integ_test = "test:integration" in scripts or "test:e2e" in scripts
    if has_integ_test:
        integ_script = "test:integration" if "test:integration" in scripts else "test:e2e"
        integ_cmd = f"{run} run {integ_script}"
    else:
        integ_cmd = "echo 'No integration test script found — skipping'"

    stages.append(
        Stage(
            id="integration_test",
            agent=AgentType.TEST,
            command=integ_cmd,
            depends_on=["security_scan"],
            timeout_seconds=300,
            critical=False,
        )
    )

    deploy_depends = ["integration_test"]

    # Stage 6: Deploy or Run (if goal matches)
    deploy_keywords = ["deploy", "release", "publish", "production", "staging"]
    run_keywords = ["run", "execute", "start", "local"]
    docker_keywords = ["docker", "container", "image", "package"]

    should_deploy = any(kw in goal.lower() for kw in deploy_keywords)
    should_run = any(kw in goal.lower() for kw in run_keywords)
    should_docker = any(kw in goal.lower() for kw in docker_keywords) or analysis.deploy_target == "docker"

    if should_docker:
        stages.append(
            Stage(
                id="docker_build",
                agent=AgentType.BUILD,
                command=f"docker build -t app:{analysis.language} .",
                depends_on=["build"],
                timeout_seconds=600,
            )
        )
        if should_run or analysis.deploy_target == "docker":
            stages.append(
                Stage(
                    id="docker_run",
                    agent=AgentType.DEPLOY,
                    command=f"docker run -d -p 3000:3000 --name app_{analysis.language} app:{analysis.language}",
                    depends_on=["docker_build"],
                    timeout_seconds=300,
                )
            )
            stages.append(
                Stage(
                    id="health_check_docker",
                    agent=AgentType.VERIFY,
                    command="sleep 5 && curl -s -o /dev/null -w '%{http_code}' http://localhost:3000 | grep -q 200",
                    depends_on=["docker_run"],
                    timeout_seconds=120,
                    retry_count=2,
                    critical=True,
                )
            )

    elif should_deploy or should_run:
        target_port = 3000
        kill_port = f"fuser -k {target_port}/tcp 2>/dev/null || true"

        if has_build:
            # Static React/Next app — use serve (instant, no webpack)
            # Bind to 0.0.0.0 to be accessible from host
            server_cmd = f"serve -s build -l 0.0.0.0:{target_port}"
        elif "start" in scripts:
            # Express/Node server - bind to 0.0.0.0
            server_cmd = f"HOST=0.0.0.0 PORT={target_port} NODE_ENV=production {run} start"
        elif "deploy" in scripts:
            server_cmd = f"HOST=0.0.0.0 PORT={target_port} {run} run deploy"
        else:
            server_cmd = "echo 'No start/deploy script found — skipping'"

        # Use script-based backgrounding to ensure proper detachment from parent pipes
        # Prefix is handled inside the script as a separate cd command if needed
        script_prefix = f"cd {subdir}" if subdir else "echo 'No subdir prefix needed'"
        bg_cmd = (
            f"cat > /tmp/start_node_app.sh << 'SCRIPT_EOF'\n"
            f"#!/bin/bash\n"
            f"{script_prefix}\n"
            f"{kill_port}\n"
            f"{server_cmd}\n"
            f"SCRIPT_EOF\n"
            f"chmod +x /tmp/start_node_app.sh && "
            f"(nohup /tmp/start_node_app.sh > /tmp/app.log 2>&1 < /dev/null &) && sleep 5"
        )

        stage_id = "deploy" if should_deploy else "run"
        hc_id = "health_check" if should_deploy else "health_check_run"
        deploy_cmd = get_deploy_command(analysis.deploy_target, analysis.has_dockerfile, bg_cmd)

        stages.append(
            Stage(
                id=stage_id,
                agent=AgentType.DEPLOY,
                command=deploy_cmd,
                depends_on=deploy_depends,
                timeout_seconds=300,
            )
        )
        stages.append(
            Stage(
                id=hc_id,
                agent=AgentType.VERIFY,
                command=get_health_check_command(analysis.deploy_target, default_port=target_port, log_file="/tmp/app.log"),
                depends_on=[stage_id],
                timeout_seconds=120,
            )
        )

    return stages
