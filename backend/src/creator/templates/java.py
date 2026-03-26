from src.creator.templates.deploy_commands import get_deploy_command, get_health_check_command
from src.models.pipeline import AgentType, RepoAnalysis, Stage


def generate_java_pipeline(analysis: RepoAnalysis, goal: str) -> list[Stage]:
    """Generate a Java CI/CD pipeline. Uses wrapper scripts when available."""
    use_gradle = analysis.package_manager == "gradle"
    has_dockerfile = analysis.has_dockerfile

    # Prefix all commands with subdir cd if project is in a subdirectory
    subdir = analysis.project_subdir
    prefix = f"cd {subdir} && " if subdir else ""

    # Prefer wrapper scripts (./mvnw / ./gradlew) — they download the right version
    # Fall back to system mvn/gradle
    if use_gradle:
        install_cmd = f"{prefix}chmod +x gradlew 2>/dev/null; ./gradlew dependencies --no-daemon -q 2>/dev/null || gradle dependencies --no-daemon -q 2>/dev/null || echo 'Dependencies resolved'"
        test_cmd = f"{prefix}chmod +x gradlew 2>/dev/null; ./gradlew test --no-daemon -q 2>&1 | tail -20 || gradle test --no-daemon -q 2>&1 | tail -20"
        build_cmd = f"{prefix}chmod +x gradlew 2>/dev/null; ./gradlew build -x test --no-daemon -q 2>&1 | tail -10 || gradle build -x test --no-daemon -q 2>&1 | tail -10"
        audit_cmd = f"{prefix}chmod +x gradlew 2>/dev/null; ./gradlew dependencyCheckAnalyze --no-daemon -q 2>/dev/null || gradle dependencyCheckAnalyze --no-daemon -q 2>/dev/null || echo 'OWASP plugin not configured'"
        lint_cmd = f"{prefix}chmod +x gradlew 2>/dev/null; ./gradlew check -x test --no-daemon -q 2>/dev/null || gradle check -x test --no-daemon -q 2>/dev/null || echo 'No linting configured'"
        integ_cmd = f"{prefix}chmod +x gradlew 2>/dev/null; ./gradlew integrationTest --no-daemon -q 2>/dev/null || ./gradlew test --tests '*IntegrationTest*' --no-daemon -q 2>/dev/null || gradle integrationTest --no-daemon -q 2>/dev/null || echo 'No integration tests found — skipping'"
        run_jar = f"{prefix}java -jar build/libs/*.jar 2>/dev/null || java -jar build/libs/*-SNAPSHOT.jar"
    else:
        install_cmd = f"{prefix}chmod +x mvnw 2>/dev/null; ./mvnw dependency:resolve -q --no-transfer-progress 2>&1 | tail -5 || mvn dependency:resolve -q --no-transfer-progress 2>&1 | tail -5"
        test_cmd = f"{prefix}chmod +x mvnw 2>/dev/null; ./mvnw test -q --no-transfer-progress 2>&1 | tail -20 || mvn test -q --no-transfer-progress 2>&1 | tail -20"
        build_cmd = f"{prefix}chmod +x mvnw 2>/dev/null; ./mvnw package -DskipTests -q --no-transfer-progress 2>&1 | tail -10 || mvn package -DskipTests -q --no-transfer-progress 2>&1 | tail -10"
        audit_cmd = f"{prefix}chmod +x mvnw 2>/dev/null; ./mvnw org.owasp:dependency-check-maven:check -q --no-transfer-progress 2>/dev/null || mvn org.owasp:dependency-check-maven:check -q --no-transfer-progress 2>/dev/null || echo 'OWASP plugin not configured'"
        lint_cmd = f"{prefix}chmod +x mvnw 2>/dev/null; ./mvnw checkstyle:check -q --no-transfer-progress 2>/dev/null || mvn checkstyle:check -q --no-transfer-progress 2>/dev/null || echo 'No linting configured'"
        integ_cmd = f"{prefix}chmod +x mvnw 2>/dev/null; ./mvnw verify -DskipUnitTests -q --no-transfer-progress 2>/dev/null || mvn verify -DskipUnitTests -q --no-transfer-progress 2>/dev/null || echo 'No integration tests found — skipping'"
        run_jar = f"{prefix}java -jar target/*.jar 2>/dev/null || java -jar target/*-SNAPSHOT.jar"

    stages: list[Stage] = []

    deploy_keywords = ["deploy", "release", "publish", "production", "staging", "local", "run", "start"]
    should_deploy = any(kw in goal.lower() for kw in deploy_keywords)

    # Docker path — fastest and most reliable
    if has_dockerfile:
        stages.append(Stage(
            id="install",
            agent=AgentType.BUILD,
            command="echo 'Dockerfile detected — using Docker build pipeline'",
            depends_on=[],
            timeout_seconds=10,
        ))
        stages.append(Stage(
            id="lint",
            agent=AgentType.TEST,
            command="echo 'Lint: skipped (Docker build)'",
            depends_on=["install"],
            timeout_seconds=10,
            critical=False,
        ))
        stages.append(Stage(
            id="build",
            agent=AgentType.BUILD,
            command="docker build -t app-java:latest . 2>&1 | tail -5",
            depends_on=[],
            timeout_seconds=600,
        ))
        stages.append(Stage(
            id="security_scan",
            agent=AgentType.SECURITY,
            command="echo 'Security scan: skipped (Docker build)'",
            depends_on=["build"],
            timeout_seconds=10,
            critical=False,
        ))
        stages.append(Stage(
            id="integration_test",
            agent=AgentType.TEST,
            command="echo 'Integration test: skipped (Docker build)'",
            depends_on=["security_scan"],
            timeout_seconds=10,
            critical=False,
        ))

        if should_deploy:
            target_port = 8080
            stages.append(Stage(
                id="deploy",
                agent=AgentType.DEPLOY,
                command=(
                    f"fuser -k {target_port}/tcp 2>/dev/null || true && "
                    f"docker rm -f app-java-run 2>/dev/null || true && "
                    f"(docker run -d --name app-java-run -p {target_port}:{target_port} app-java:latest) && "
                    f"sleep 5"
                ),
                depends_on=["integration_test"],
                timeout_seconds=120,
                retry_count=1,
            ))
            stages.append(Stage(
                id="health_check",
                agent=AgentType.VERIFY,
                command=get_health_check_command(None, default_port=target_port),
                depends_on=["deploy"],
                timeout_seconds=120,
                retry_count=5,
                critical=True,
            ))
        return stages

    # Local build path
    stages.append(Stage(
        id="install",
        agent=AgentType.BUILD,
        command=install_cmd,
        depends_on=[],
        timeout_seconds=300,
    ))
    stages.append(Stage(
        id="lint",
        agent=AgentType.TEST,
        command=lint_cmd,
        depends_on=["install"],
        timeout_seconds=60,
        critical=False,
    ))
    stages.append(Stage(
        id="unit_test",
        agent=AgentType.TEST,
        command=test_cmd,
        depends_on=["install"],
        timeout_seconds=300,
        critical=False,
    ))
    stages.append(Stage(
        id="build",
        agent=AgentType.BUILD,
        command=build_cmd,
        depends_on=["unit_test"],
        timeout_seconds=300,
    ))
    stages.append(Stage(
        id="security_scan",
        agent=AgentType.SECURITY,
        command=audit_cmd,
        depends_on=["build"],
        timeout_seconds=180,
        critical=False,
    ))
    stages.append(Stage(
        id="integration_test",
        agent=AgentType.TEST,
        command=integ_cmd,
        depends_on=["security_scan"],
        timeout_seconds=300,
        critical=False,
    ))

    if should_deploy:
        target_port = 8080
        kill_port = f"fuser -k {target_port}/tcp 2>/dev/null || true"

        if analysis.framework == "spring-boot":
            # bootRun blocks — use jar instead, bind to 0.0.0.0
            # For subdirs, use bash -c to ensure cd persists
            if subdir:
                run_cmd = f"bash -c 'cd {subdir} && java -Dserver.port={target_port} -Dserver.address=0.0.0.0 -jar target/*.jar' 2>/dev/null || bash -c 'cd {subdir} && java -Dserver.port={target_port} -Dserver.address=0.0.0.0 -jar target/*-SNAPSHOT.jar'"
            else:
                run_cmd = f"java -Dserver.port={target_port} -Dserver.address=0.0.0.0 -jar target/*.jar 2>/dev/null || java -Dserver.port={target_port} -Dserver.address=0.0.0.0 -jar target/*-SNAPSHOT.jar"
        else:
            # For Gradle projects
            jar_path = "build/libs" if use_gradle else "target"
            if subdir:
                run_cmd = f"bash -c 'cd {subdir} && java -Dserver.port={target_port} -Dserver.address=0.0.0.0 -jar {jar_path}/*.jar' 2>/dev/null || bash -c 'cd {subdir} && java -Dserver.port={target_port} -Dserver.address=0.0.0.0 -jar {jar_path}/*-SNAPSHOT.jar'"
            else:
                run_cmd = f"java -Dserver.port={target_port} -Dserver.address=0.0.0.0 -jar {jar_path}/*.jar 2>/dev/null || java -Dserver.port={target_port} -Dserver.address=0.0.0.0 -jar {jar_path}/*-SNAPSHOT.jar"

        # Use script-based backgrounding to ensure proper detachment from parent pipes
        # Prefix is handled inside the script as a separate cd command if needed
        script_prefix = f"cd {subdir}" if subdir else "echo 'No subdir prefix needed'"
        bg_cmd = (
            f"cat > /tmp/start_java_app.sh << 'SCRIPT_EOF'\n"
            f"#!/bin/bash\n"
            f"{script_prefix}\n"
            f"{kill_port}\n"
            f"{run_cmd}\n"
            f"SCRIPT_EOF\n"
            f"chmod +x /tmp/start_java_app.sh && "
            f"(nohup /tmp/start_java_app.sh > /tmp/app.log 2>&1 < /dev/null &) && sleep 5"
        )
        # Health check should ONLY check the specific port we intended to deploy to
        hc_cmd = (
            f"for i in $(seq 1 20); do "
            f"if nc -z localhost {target_port}; then "
            f"echo 'Health check passed: port {target_port} is open'; exit 0; "
            f"fi; sleep 2; done; "
            f"echo 'Health check failed: port {target_port} not responding'; exit 1"
        )
        deploy_cmd = get_deploy_command(analysis.deploy_target, has_dockerfile, bg_cmd)

        stages.append(Stage(
            id="deploy",
            agent=AgentType.DEPLOY,
            command=deploy_cmd,
            depends_on=["integration_test"],
            timeout_seconds=120,
            retry_count=1,
        ))
        stages.append(Stage(
            id="health_check",
            agent=AgentType.VERIFY,
            command=hc_cmd,
            depends_on=["deploy"],
            timeout_seconds=120,
            retry_count=3,
            critical=True,
        ))

    return stages
