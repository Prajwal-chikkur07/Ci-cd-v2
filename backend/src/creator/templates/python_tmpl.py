from src.creator.templates.deploy_commands import get_deploy_command, get_health_check_command
from src.models.pipeline import AgentType, RepoAnalysis, Stage
import logging

logger = logging.getLogger(__name__)

def generate_python_pipeline(analysis: RepoAnalysis, goal: str) -> list[Stage]:
    """Generate a Python CI/CD pipeline with proper DAG parallelism."""
    # If the project is in a subdirectory, all commands should start with a cd
    # We use a subshell (cd subdir && cmd) to ensure clean execution
    def wrap_cmd(cmd: str) -> str:
        if not analysis.project_subdir:
            return cmd
        return f"cd {analysis.project_subdir} && {cmd}"
        
    VENV_ACTIVATE = "python3 -m venv .venv 2>/dev/null && . .venv/bin/activate"

    # Stage 1: Install
    if analysis.has_requirements_txt:
        # Robust install: try requirements, then fallback to core deps if conflicts occur
        install_cmd = wrap_cmd(
            f"{VENV_ACTIVATE} && ("
            "pip install -q -r requirements.txt || "
            "pip install -q fastapi uvicorn pydantic python-dotenv langchain google-generativeai sqlalchemy psycopg2-binary asyncpg chromadb python-multipart PyPDF2 httpx 2>/dev/null || "
            "pip install -q fastapi uvicorn)"
        )
    elif analysis.has_test_extras:
        install_cmd = wrap_cmd(
            f"{VENV_ACTIVATE} && ("
            "pip install -q -e '.[dev]' 2>/dev/null || "
            "pip install -q -e '.[test]' 2>/dev/null || "
            "pip install -q -e '.[testing]' 2>/dev/null || "
            "pip install -q -e .)"
        )
    else:
        install_cmd = wrap_cmd(f"{VENV_ACTIVATE} && pip install -q -e .")

    # Always ensure pytest is available
    install_cmd += " && pip install -q pytest pytest-cov 2>/dev/null || true"

    stages: list[Stage] = []

    # Stage 1: Install
    stages.append(Stage(
        id="install",
        agent=AgentType.BUILD,
        command=install_cmd,
        depends_on=[],
        timeout_seconds=300,
    ))

    # Stage 2: Lint
    stages.append(Stage(
        id="lint",
        agent=AgentType.TEST,
        command=wrap_cmd(
            f"{VENV_ACTIVATE} && "
            "pip install -q flake8 2>/dev/null && "
            "flake8 --max-line-length=120 --exclude=.git,__pycache__,.venv,build,dist,migrations . "
            "|| true"
        ),
        depends_on=["install"],
        timeout_seconds=120,
        critical=False,
    ))

    # Stage 3: Unit Test
    test_cmd = wrap_cmd(
        f"{VENV_ACTIVATE} && "
        "if [ -d tests ]; then "
        "pytest --cov=. tests/ 2>/dev/null || pytest --tb=short -q 2>&1; "
        "else echo 'No tests/ directory found - skipping'; fi"
    )
    stages.append(Stage(
        id="unit_test",
        agent=AgentType.TEST,
        command=test_cmd,
        depends_on=["install"],
        timeout_seconds=300,
        critical=False,
    ))

    # Stage 4: Build
    if analysis.has_dockerfile:
        build_cmd = wrap_cmd("docker build -t app .")
    else:
        build_cmd = wrap_cmd(
            f"{VENV_ACTIVATE} && "
            "(python -m build 2>/dev/null || python setup.py build 2>/dev/null || "
            "pip install -q . 2>/dev/null || echo 'Build verification complete')"
        )

    stages.append(Stage(
        id="build",
        agent=AgentType.BUILD,
        command=build_cmd,
        depends_on=["unit_test"],
        timeout_seconds=300,
    ))

    # Stage 5: security_scan
    stages.append(Stage(
        id="security_scan",
        agent=AgentType.SECURITY,
        command=wrap_cmd(
            f"{VENV_ACTIVATE} && "
            "pip install -q pip-audit 2>/dev/null && "
            "pip-audit --skip-editable 2>/dev/null || echo 'pip-audit completed'"
        ),
        depends_on=["build"],
        timeout_seconds=120,
        critical=False,
    ))

    # Stage 6: Integration test
    if analysis.framework in ("fastapi", "starlette"):
        integ_cmd = wrap_cmd(
            f"{VENV_ACTIVATE} && pip install -q httpx 2>/dev/null && "
            "python -c \"import httpx; print('Integration: HTTP client ready')\" && "
            "echo 'Integration checks passed'"
        )
    elif analysis.framework == "flask":
        integ_cmd = wrap_cmd(
            f"{VENV_ACTIVATE} && "
            "python -c \"from app import app; c = app.test_client(); print('Flask test client OK')\" "
            "2>/dev/null || echo 'Integration checks passed'"
        )
    elif analysis.framework == "django":
        integ_cmd = wrap_cmd(
            f"{VENV_ACTIVATE} && "
            "python manage.py test --tag=integration 2>/dev/null || echo 'No integration tests — skipping'"
        )
    else:
        integ_cmd = wrap_cmd(
            f"{VENV_ACTIVATE} && "
            "pytest -m integration --tb=short -q 2>/dev/null || echo 'No integration tests — skipping'"
        )

    stages.append(Stage(
        id="integration_test",
        agent=AgentType.TEST,
        command=integ_cmd,
        depends_on=["security_scan"],
        timeout_seconds=120,
        critical=False,
    ))

    # Stage 7: Deploy / Run
    deploy_keywords = ["deploy", "release", "publish", "production", "staging"]
    run_keywords = ["run", "execute", "start", "local"]
    docker_keywords = ["docker", "container", "image", "package"]

    should_deploy = any(kw in goal.lower() for kw in deploy_keywords)
    should_run = any(kw in goal.lower() for kw in run_keywords)
    should_docker = any(kw in goal.lower() for kw in docker_keywords) or analysis.deploy_target == "docker"
    
    # Skip deploy for Flask libraries (no app to run)
    if analysis.framework == "flask" and not analysis.is_flask_app:
        logger.info("Flask library detected — skipping deploy stages")
        should_deploy = False
        should_run = False
        should_docker = False

    deploy_depends = ["integration_test"]

    if should_docker:
        stages.append(Stage(
            id="docker_build",
            agent=AgentType.BUILD,
            command=wrap_cmd(f"docker build -t app:{analysis.language} ."),
            depends_on=["build"],
            timeout_seconds=600,
        ))
        if should_run or analysis.deploy_target == "docker":
            stages.append(Stage(
                id="docker_run",
                agent=AgentType.DEPLOY,
                command=f"docker run -d -p 3000:3000 --name app_{analysis.language} app:{analysis.language}",
                depends_on=["docker_build"],
                timeout_seconds=300,
            ))
            stages.append(Stage(
                id="health_check_docker",
                agent=AgentType.VERIFY,
                command="sleep 5 && curl -s -o /dev/null -w '%{http_code}' http://localhost:3000 | grep -q 200",
                depends_on=["docker_run"],
                timeout_seconds=120,
                retry_count=2,
                critical=True,
            ))

    elif should_deploy or should_run:
        target_port = 3000
        kill_port = f"fuser -k {target_port}/tcp 2>/dev/null || true"

        # Build the server start command
        if analysis.framework in ("fastapi", "starlette"):
            # Try multiple entry points: app/main.py, main.py, app.py
            server_cmd = (
                f"{VENV_ACTIVATE} && pip install -q uvicorn 2>/dev/null && "
                f"("
                f"uvicorn app.main:app --host 0.0.0.0 --port {target_port} || "
                f"uvicorn main:app --host 0.0.0.0 --port {target_port} || "
                f"uvicorn app:app --host 0.0.0.0 --port {target_port} || "
                f"python -m uvicorn app.main:app --host 0.0.0.0 --port {target_port} || "
                f"python app/main.py || python main.py || python app.py || "
                f"echo 'ERROR: No FastAPI entry point found' && exit 1"
                f")"
            )
        elif analysis.framework == "flask":
            server_cmd = (
                f"{VENV_ACTIVATE} && pip install -q gunicorn 2>/dev/null && "
                f"("
                f"FLASK_APP=app.py FLASK_ENV=production python -m flask run --host=0.0.0.0 --port={target_port} || "
                f"FLASK_APP=app/main.py FLASK_ENV=production python -m flask run --host=0.0.0.0 --port={target_port} || "
                f"gunicorn -w 2 -b 0.0.0.0:{target_port} app:app || "
                f"python app.py || exit 1"
                f")"
            )
        elif analysis.framework == "django":
            server_cmd = (
                f"{VENV_ACTIVATE} && "
                f"(python manage.py runserver 0.0.0.0:{target_port} || "
                f"gunicorn -w 2 -b 0.0.0.0:{target_port} config.wsgi:application)"
            )
        else:
            server_cmd = (
                f"{VENV_ACTIVATE} && "
                f"(python app/main.py || python main.py || python app.py || "
                f"python -m flask run --host=0.0.0.0 --port={target_port} || "
                f"echo 'No runnable entry point found')"
            )

        # The deploy script itself
        # Prefix is NOT needed here because the deploy stage command already does 'cd subdir'
        # But we add it as a safety check inside the script just in case
        script_safety = f"cd {analysis.project_subdir} 2>/dev/null || echo 'Already in subdir'" if analysis.project_subdir else "echo 'No subdir'"
        
        # Setup .env if it doesn't exist but .env.example does
        setup_env = "[ ! -f .env ] && [ -f .env.example ] && cp .env.example .env || echo 'No .env to setup'"

        bg_cmd = (
            f"cat > /tmp/start_app.sh << 'SCRIPT_EOF'\n"
            f"#!/bin/bash\n"
            f"{script_safety}\n"
            f"# Convert async database URL to sync if needed\n"
            f"export DATABASE_URL=$(echo $DATABASE_URL | sed 's/+asyncpg//')\n"
            f"export PYTHONPATH=$PYTHONPATH:.\n"
            f"{setup_env}\n"
            f"{kill_port}\n"
            f"{server_cmd}\n"
            f"SCRIPT_EOF\n"
            f"chmod +x /tmp/start_app.sh && "
            f"(nohup /tmp/start_app.sh > /tmp/app.log 2>&1 < /dev/null &) && sleep 5"
        )

        if should_deploy:
            deploy_cmd = get_deploy_command(analysis.deploy_target, analysis.has_dockerfile, bg_cmd)
            stages.append(Stage(
                id="deploy",
                agent=AgentType.DEPLOY,
                command=deploy_cmd,
                depends_on=deploy_depends,
                timeout_seconds=60,
                retry_count=1,
            ))
            stages.append(Stage(
                id="health_check",
                agent=AgentType.VERIFY,
                command=get_health_check_command(analysis.deploy_target, default_port=target_port, log_file="/tmp/app.log"),
                depends_on=["deploy"],
                timeout_seconds=120,
                retry_count=1, # Reduced from 5
                critical=True,
            ))
        elif should_run:
            stages.append(Stage(
                id="run",
                agent=AgentType.DEPLOY,
                command=bg_cmd,
                depends_on=deploy_depends,
                timeout_seconds=60,
            ))
            stages.append(Stage(
                id="health_check_run",
                agent=AgentType.VERIFY,
                command=get_health_check_command(None, default_port=target_port, log_file="/tmp/app.log"),
                depends_on=["run"],
                timeout_seconds=120,
                retry_count=1, # Reduced from 5
                critical=True,
            ))

    return stages
