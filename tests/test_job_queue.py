from kirolets_bot.job_queue import QueuedJob, deserialize_job, serialize_job


def test_queued_job_round_trip():
    job = QueuedJob(
        id="job-1",
        chat_id=123,
        user_label="giusedroid",
        kind="text",
        text="Do the thing",
    )

    assert deserialize_job(serialize_job(job)) == job
