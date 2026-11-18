"""Jobs: real processes, their exit status, timeout, cancellation and reattachment after a restart."""

import time
import unittest

from research_pipeline import jobs
from research_pipeline.state import Job
from tests.helpers import remove, temp_project


class JobsTest(unittest.TestCase):
    def setUp(self):
        self.root = temp_project()
        (self.root / "agents" / "a").mkdir(parents=True)

    def tearDown(self):
        remove(self.root)

    def job(self, command, timeout=30):
        return Job("job-1", "a", command, str(self.root / "agents" / "a"), timeout, time.time())

    def wait(self, job, process):
        for _ in range(200):
            if jobs.poll(self.root, job, process):
                return
            time.sleep(0.05)
        self.fail(f"{job.command} did not end")

    def test_job_files_are_never_written_through_a_symlink(self):
        outside = self.root.parent / f"{self.root.name}-outside.txt"
        outside.write_text("keep\n")
        self.addCleanup(outside.unlink)
        folder = self.root / "agents" / "a" / "jobs"
        folder.mkdir()
        (folder / "FOLDER_CONTENT.md").symlink_to(outside)  # the owner can write its own folder
        with self.assertRaises(ValueError):
            jobs.write_index(self.root, "a", [self.job("true")])
        (folder / "job-1").mkdir()
        (folder / "job-1" / "stdout.log").symlink_to(outside)
        with self.assertRaises(ValueError):
            jobs.start(self.root, self.job("echo overwritten"))
        self.assertEqual(outside.read_text(), "keep\n")

    def test_finished_and_failed(self):
        job = self.job("echo hello; echo oops >&2")
        self.wait(job, jobs.start(self.root, job))
        self.assertEqual((job.status, job.exit_code), ("finished", 0))
        description = jobs.describe(self.root, job)
        self.assertIn("hello", description)
        self.assertIn("oops", description)
        failing = self.job("exit 3")
        self.wait(failing, jobs.start(self.root, failing))
        self.assertEqual((failing.status, failing.exit_code), ("failed", 3))

    def test_timeout_is_enforced_by_the_job_itself(self):
        job = self.job("sleep 30", timeout=0.5)
        process = jobs.start(self.root, job)
        self.wait(job, process)
        self.assertEqual(job.status, "timeout")

    def test_cancel_stops_descendants(self):
        job = self.job("sleep 60 & sleep 60 & wait")
        process = jobs.start(self.root, job)
        time.sleep(0.3)
        self.assertGreaterEqual(len(jobs._session_members(job.pid, job.ticks)), 3)
        jobs.cancel(job)
        process.wait(5)
        self.assertEqual(job.status, "cancelled")
        self.assertEqual(jobs._session_members(job.pid, job.ticks), [])

    def test_reattach_after_restart_reads_the_exit_file(self):
        job = self.job("sleep 0.5; echo late")
        process = jobs.start(self.root, job)
        self.assertFalse(jobs.poll(self.root, job, None))  # a restarted controller has no process object
        process.wait(5)  # (only to reap it in this test)
        self.assertTrue(jobs.poll(self.root, job, None))
        self.assertEqual(job.status, "finished")


if __name__ == "__main__":
    unittest.main()
