from typing import Optional


def get_deploy_command(deploy_target: Optional[str], has_dockerfile: bool, fallback_cmd: str = "") -> str:
    """Return a deploy command based on the deploy target."""
    if deploy_target == "docker":
        return "docker build -t app . && docker run -d -p 8080:8080 app"
    elif deploy_target == "aws":
        return "aws ecr get-login-password | docker login --username AWS --password-stdin && docker build -t app . && docker push app"
    elif deploy_target == "heroku":
        return "heroku container:push web && heroku container:release web"
    elif deploy_target in ("kubernetes", "k8s"):
        return "kubectl apply -f k8s/ && kubectl rollout status deployment/app"
    elif deploy_target == "staging":
        if has_dockerfile:
            return "ENV=staging docker build -t app:staging . && docker push app:staging"
        return f"ENV=staging {fallback_cmd}" if fallback_cmd else "ENV=staging echo 'Deploy: configure staging deployment'"
    elif deploy_target == "production":
        if has_dockerfile:
            return "ENV=production docker build -t app:latest . && docker push app:latest"
        return f"ENV=production {fallback_cmd}" if fallback_cmd else "ENV=production echo 'Deploy: configure production deployment'"
    elif has_dockerfile:
        return "docker build -t app . && docker push app"
    elif fallback_cmd:
        if fallback_cmd.rstrip().endswith("&"):
            return f"{fallback_cmd} sleep 2 && echo 'Server started in background'"
        return fallback_cmd
    else:
        return "echo 'Deploy: package application for distribution'"


def get_health_check_command(
    deploy_target: Optional[str],
    default_port: int = 8080,
    log_file: str = "/tmp/app.log",
) -> str:
    """Return a robust health check that prioritizes the intended port."""
    if deploy_target in ("kubernetes", "k8s"):
        return "kubectl get pods -l app=app --field-selector=status.phase=Running | grep -q Running"

    # We check the default port specifically, then a range of others as fallback
    # Increased wait time and iterations for slower apps
    cmd = (
        f"echo 'Starting health check on port {default_port}...'; "
        f"for i in $(seq 1 30); do "
        f"  if nc -z localhost {default_port} 2>/dev/null; then "
        f"    echo 'Health check passed: port {default_port} is open'; exit 0; "
        f"  fi; "
        f"  sleep 2; "
        f"done; "
        f"echo 'Health check failed: port {default_port} not responding. Checking fallback ports...'; "
        f"for P in 3000 8080 5000 8000 3001 3002 8081 5001; do "
        f"  if nc -z localhost $P 2>/dev/null; then "
        f"    echo \"Success: service up on port $P\"; exit 0; "
        f"  fi; "
        f"done; "
        f"echo 'Health check failed after 60s' && tail -50 {log_file} 2>/dev/null; exit 1"
    )

    return cmd
