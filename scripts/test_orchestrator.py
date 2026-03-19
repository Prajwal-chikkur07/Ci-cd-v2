import asyncio
import httpx
import os
import sys
from pathlib import Path

BASE_URL = "http://localhost:8001"
FIXTURES_DIR = Path(__file__).parent.parent / "tests" / "fixtures"

TEST_CASES = [
    {
        "name": "Basic Node.js Run",
        "fixture": "node-basic",
        "goal": "build and start",
        "expected_status": "success",
    },
    {
        "name": "Dockerize Node App",
        "fixture": "node-docker",
        "goal": "dockerize and run on port 3000",
        "expected_status": "success",
    },
    {
        "name": "Dependency Typo (Self-Healing)",
        "fixture": "node-typo",
        "goal": "build and start",
        "expected_status": "success",
        "expect_recovery": True,
    },
    {
        "name": "Missing Start Script (Self-Healing)",
        "fixture": "node-no-start",
        "goal": "run the app",
        "expected_status": "success",
        "expect_recovery": True,
    },
    {
        "name": "Port Mismatch (Auto-Recovery)",
        "fixture": "node-wrong-port",
        "goal": "run on port 3000",
        "expected_status": "success",
    }
]

async def run_test(client: httpx.AsyncClient, test: dict):
    print(f"\n--- Testing: {test['name']} ---")
    # Resolve absolute path for the backend to use
    fixture_path = str(FIXTURES_DIR.resolve() / test['fixture'])
    
    # 1. Create Pipeline
    print(f"Creating pipeline for {fixture_path}...")
    try:
        resp = await client.post(
            f"{BASE_URL}/pipelines",
            params={
                "repo_url": f"file://{fixture_path}",
                "goal": test['goal'],
                "name": test['name']
            }
        )
    except Exception as e:
        print(f"FAILED to connect to backend: {e}")
        return False

    if resp.status_code != 200:
        print(f"FAILED to create pipeline: {resp.text}")
        return False
    
    spec = resp.json()
    pipeline_id = spec['pipeline_id']
    print(f"Pipeline created: {pipeline_id}")
    
    # 2. Execute Pipeline
    print(f"Executing pipeline...")
    await client.post(f"{BASE_URL}/pipelines/{pipeline_id}/execute")
    
    # 3. Poll for results
    print("Waiting for completion...")
    while True:
        resp = await client.get(f"{BASE_URL}/pipelines/{pipeline_id}/results")
        if resp.status_code == 200:
            results = resp.json()
            if not results:
                await asyncio.sleep(2)
                continue

            # Check if all stages are finished
            all_finished = True
            has_failed = False
            for stage_id, res in results.items():
                if res['status'] in ('running', 'pending'):
                    all_finished = False
                if res['status'] == 'failed':
                    has_failed = True
            
            if all_finished:
                overall = "failed" if has_failed else "success"
                print(f"Pipeline Finished: {overall.upper()}")
                
                # Check for recovery logs in results or through direct inspect
                if test.get('expect_recovery'):
                    print("Checking for self-healing indicator...")
                    # In this system, recovery might be in stderr or metadata
                    recovery_applied = any(
                        "recovery" in str(r).lower() or 
                        "retry" in str(r).lower() or 
                        "fixed" in str(r).lower() 
                        for r in results.values()
                    )
                    if recovery_applied:
                        print("✅ Self-healing recovery was likely applied.")
                
                if overall == test['expected_status']:
                    print(f"✅ Test Passed: {test['name']}")
                    return True
                else:
                    print(f"❌ Test Failed: Expected {test['expected_status']}, got {overall}")
                    return False
        
        await asyncio.sleep(2)

async def main():
    print("Starting CI/CD Orchestrator Test Suite...")
    async with httpx.AsyncClient(timeout=600) as client:
        passed = 0
        for test in TEST_CASES:
            try:
                if await run_test(client, test):
                    passed += 1
            except Exception as e:
                print(f"Error running test {test['name']}: {e}")
        
        print(f"\nSummary: {passed}/{len(TEST_CASES)} tests passed.")
        if passed < len(TEST_CASES):
            sys.exit(1)

if __name__ == "__main__":
    asyncio.run(main())
