import json
import time
from pathlib import Path

import boto3
import docker
import pytest
from botocore.config import Config

current_dir = Path(__file__).resolve().parent
Path("./outputs").mkdir(exist_ok=True)

STATE_MACHINE_NAME = "LambdaSQSIntegration"


@pytest.fixture(scope="module")
def stepfunctions_url():
    """Fixture to start Step Functions Local in a Docker container."""

    mock_config_destination = "/home/StepFunctionsLocal/state_machine_mock_config.json"

    client = docker.from_env()
    container = client.containers.run(
        "amazon/aws-stepfunctions-local",
        ports={"8083/tcp": 8083},
        detach=True,
        volumes={
            f"{current_dir}/state_machine_mock_config.json": {
                "bind": mock_config_destination,
                "mode": "ro",
            }
        },
        environment={
            "SFN_MOCK_CONFIG": mock_config_destination,
        },
    )

    try:
        print("Waiting for Step Functions Local to start...")
        time.sleep(5)
        yield "http://localhost:8083"

    finally:
        container.stop()
        print("Stopping Step Functions Local...")
        container.remove()
        print("Step Functions Local stopped.")


@pytest.fixture(scope="module")
def stepfunctions_client(stepfunctions_url):
    """Fixture to create a Step Functions client with the Step Functions Local endpoint."""

    config = Config(region_name="us-central-1")
    yield boto3.client(
        "stepfunctions",
        endpoint_url=stepfunctions_url,
        config=config,
    )


@pytest.fixture(scope="module")
def state_machine_arn(stepfunctions_client):
    """Fixture to create a state machine and return its ARN."""

    with open("state_machine_definition.asl.json", "r") as file:
        state_machine_definition = json.load(file)

    response = stepfunctions_client.create_state_machine(
        name=STATE_MACHINE_NAME,
        definition=json.dumps(state_machine_definition),
        roleArn="arn:aws:iam::123456789012:role/DummyRole",
    )

    state_machine_arn = response["stateMachineArn"]
    assert "stateMachineArn" in response

    yield state_machine_arn


@pytest.mark.parametrize("test_name", ["LambdaSuccess", "LambdaError"])
def test_execution(test_name, state_machine_arn, stepfunctions_client):
    """Test the execution of a state machine"""

    execution_response = stepfunctions_client.start_execution(
        name=test_name,
        stateMachineArn=f"{state_machine_arn}#{test_name}",
        input="{}",
    )

    while True:
        time.sleep(2)

        execution = stepfunctions_client.describe_execution(
            executionArn=execution_response["executionArn"]
        )

        if execution["status"] != "RUNNING":
            print(execution)
            break

    execution_history = stepfunctions_client.get_execution_history(
        executionArn=execution_response["executionArn"],
        reverseOrder=True,
    )

    with (
        open(f"outputs/{test_name}_execution_history.json", "w") as history_file,
        open(f"outputs/{test_name}_execution.json", "w") as execution_file,
    ):
        json.dump(execution_history, history_file, indent=4, default=str)
        json.dump(execution, execution_file, indent=4, default=str)

    assert execution["status"] == "SUCCEEDED"
