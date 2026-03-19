import asyncio
import json
import uuid
import sys
import os
from datetime import datetime
from unittest.mock import MagicMock, AsyncMock, patch

# Add src to path
sys.path.append(os.path.join(os.getcwd(), "backend"))

from src.models.pipeline import PipelineSpec, RepoAnalysis, Stage, AgentType
from src.creator.generator import generate_pipeline
from src.executor.dispatcher import PipelineExecutor, run_pipeline
from src.models.messages import StageResult, StageStatus, PipelineExecutionResult
from src.api.main import PipelineUpdate, update_pipeline

async def test_unique_stage_ids():
    print("\n--- Testing Unique Stage IDs ---")
    stages = [
        Stage(id="stage1", agent=AgentType.BUILD, command="echo 1"),
        Stage(id="stage1", agent=AgentType.BUILD, command="echo 2")
    ]
    try:
        from src.creator.generator import _validate_dag
        _validate_dag(stages)
        print("❌ Failed: Duplicate IDs not detected")
    except ValueError as e:
        print(f"✅ Success: Detected duplicate ID: {e}")

async def test_refined_logic_nodejs():
    print("\n--- Testing Refined Node.js Logic ---")
    analysis = RepoAnalysis(
        language="javascript", 
        package_manager="npm", 
        available_scripts=["start", "test"]
    )
    from src.creator.templates.nodejs import generate_nodejs_pipeline
    stages = generate_nodejs_pipeline(analysis, "Run the application locally")
    stage_ids = [s.id for s in stages]
    
    assert "unit_test" in stage_ids
    run_stage = next(s for s in stages if s.id == "run")
    assert "PORT=3000" in run_stage.command
    assert "nohup" in run_stage.command
    
    hc_stage = next(s for s in stages if s.id == "health_check_run")
    assert "3000" in hc_stage.command
    assert "grep -q 200" in hc_stage.command
    print("✅ Success: Node.js logic is correct (test, port, nohup, health)")

async def test_executor_goal_validation():
    print("\n--- Testing Executor Goal Validation ---")
    spec = PipelineSpec(
        pipeline_id="test-goal",
        name="Test",
        goal="Run application",
        analysis=RepoAnalysis(language="python", package_manager="pip"),
        stages=[]
    )
    executor = PipelineExecutor(spec)
    
    # Run goal: should look for health_check success
    results = {
        "health_check_run": StageResult(stage_id="health_check_run", status=StageStatus.SUCCESS, exit_code=0)
    }
    assert executor._validate_goal(results) == True
    
    results["health_check_run"].status = StageStatus.FAILED
    assert executor._validate_goal(results) == False
    
    # Docker goal: should look for docker_build success
    spec.goal = "Build docker image"
    results = {
        "docker_build": StageResult(stage_id="docker_build", status=StageStatus.SUCCESS, exit_code=0)
    }
    assert executor._validate_goal(results) == True
    
    results["docker_build"].status = StageStatus.FAILED
    assert executor._validate_goal(results) == False
    print("✅ Success: Goal validation logic VPC")

async def test_db_structured_results():
    print("\n--- Testing DB Structured Results ---")
    from src.db import repository as db
    
    pipeline_id = str(uuid.uuid4())
    spec = PipelineSpec(
        pipeline_id=pipeline_id,
        name="DB Test",
        goal="run",
        analysis=RepoAnalysis(language="python", package_manager="pip"),
        stages=[]
    )
    
    exec_result = PipelineExecutionResult(
        pipeline_id=pipeline_id,
        overall_status="success",
        goal_achieved=True,
        stages={"build": StageResult(stage_id="build", status=StageStatus.SUCCESS, exit_code=0)},
        duration_seconds=10.5,
        final_output={"app_url": "http://localhost:3000"}
    )
    
    # Mock session and DB calls
    # Use a simpler mocking approach to avoid coroutine issues
    with patch("src.db.repository.async_session") as mock_session:
        mock_session_instance = AsyncMock()
        mock_session.return_value.__aenter__.return_value = mock_session_instance
        
        # Mock result object returned by execute
        mock_result = MagicMock()
        mock_session_instance.execute.return_value = mock_result
        
        # Mock pipeline_row
        pipeline_row = MagicMock()
        # Ensure scalar_one_or_none is a regular mock return, not a coroutine
        mock_result.scalar_one_or_none.return_value = pipeline_row
        mock_result.scalars.return_value.all.return_value = []
        
        await db.save_results(pipeline_id, exec_result)
        assert pipeline_row.overall_status == "success"
        assert pipeline_row.goal_achieved == "true"
        print("✅ Success: DB repository correctly handles structured results")

async def main():
    await test_unique_stage_ids()
    await test_refined_logic_nodejs()
    await test_executor_goal_validation()
    await test_db_structured_results()

if __name__ == "__main__":
    asyncio.run(main())
