import json
import subprocess
import time
from pathlib import Path

import boto3
import pytest
from botocore.config import Config

current_dir = Path(__file__).resolve().parent

STATE_MACHINE_NAME = "LambdaSQSIntegration"
RUNETIME_CLI = "docker"


@pytest.fixture(scope="module")
def stepfunctions_url(cli_runtime=RUNETIME_CLI):
    """Fixture to start Step Functions Local in a Nerdctl container."""

    mock_config_destination = "/home/StepFunctionsLocal/state_machine_mock_config.json"
    container_name = "stepfunctions-local-container"

    # Command to start the container with nerdctl
    start_command = [
        cli_runtime,
        "run",
        "--name",
        container_name,
        "-p",
        "8083:8083",
        "--detach",
        "--volume",
        f"{current_dir}/state_machine_mock_config.json:{mock_config_destination}:ro",
        "--env",
        f"SFN_MOCK_CONFIG={mock_config_destination}",
        "amazon/aws-stepfunctions-local",
    ]

    # Start the container
    subprocess.run(start_command, check=True)

    try:
        print("Waiting for Step Functions Local to start...")
        time.sleep(5)
        yield "http://localhost:8083"

    finally:
        # Command to stop the container
        stop_command = [cli_runtime, "stop", container_name]
        subprocess.run(stop_command, check=True)
        print("Stopping Step Functions Local...")

        # Command to remove the container
        remove_command = [cli_runtime, "rm", container_name]
        subprocess.run(remove_command, check=True)
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
