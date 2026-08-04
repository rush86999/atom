"""
Tests for sqs_worker.process_message — DLQ + delete semantics.

A message for an unknown/unregistered task is sent to the DLQ, but it MUST
also be deleted from the main queue. The original code sent to the DLQ and
returned True (claiming "Delete from main queue") without ever calling
sqs.delete_message — so the visibility timeout expired, poll_queue
re-received the same message, re-sent it to the DLQ, and looped forever,
filling the DLQ with duplicates on every poll cycle.
"""

import json
import pytest
from unittest.mock import MagicMock

import sqs_worker


def _make_message(task_name: str, receipt_handle: str = "rh-1") -> dict:
    return {
        "MessageId": "m-1",
        "ReceiptHandle": receipt_handle,
        "Body": json.dumps({"task": task_name, "task_id": "t-1", "payload": {}}),
    }


class TestProcessMessageDlqDelete:
    @pytest.mark.asyncio
    async def test_unknown_task_is_deleted_from_main_queue_after_dlq(self, monkeypatch):
        """An unknown task sent to the DLQ must also be deleted from the main
        queue, otherwise it reappears on every poll and floods the DLQ."""
        fake_sqs = MagicMock()
        fake_sqs.send_message = MagicMock(return_value={"MessageId": "dlq-1"})
        fake_sqs.delete_message = MagicMock()
        monkeypatch.setattr(sqs_worker, "sqs", fake_sqs)
        monkeypatch.setattr(sqs_worker, "SQS_QUEUE_URL", "q-main")
        monkeypatch.setattr(sqs_worker, "SQS_DLQ_URL", "q-dlq")

        # Ensure no handler is registered for this task name.
        monkeypatch.setattr(
            sqs_worker.TaskRegistry,
            "get_handler",
            lambda name: None,
        )

        msg = _make_message("nonexistent_task")
        result = await sqs_worker.process_message(msg)

        # It was sent to the DLQ exactly once.
        assert fake_sqs.send_message.call_count == 1
        sent = fake_sqs.send_message.call_args
        assert sent.kwargs.get("QueueUrl") == "q-dlq"

        # It MUST also be deleted from the main queue (this is the bug — the
        # original code never deleted on the DLQ path, causing an infinite
        # re-receive/re-send loop).
        assert fake_sqs.delete_message.call_count == 1, (
            "Unknown task was not deleted from the main queue after DLQ send — "
            "the message will be re-received and re-sent to the DLQ on every poll."
        )
        deleted = fake_sqs.delete_message.call_args
        assert deleted.kwargs.get("QueueUrl") == "q-main"
        assert deleted.kwargs.get("ReceiptHandle") == "rh-1"
        assert result is True
