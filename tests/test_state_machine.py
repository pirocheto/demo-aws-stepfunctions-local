import json
import time
from pathlib import Path

import pytest

Path("./outputs").mkdir(exist_ok=True)


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
