"""Flask test client wrapper for JobHunt API testing."""

import json


class APIClient:
    """Wrapper around Flask test client for JobHunt API endpoints."""

    def __init__(self, flask_client):
        """Initialize with a Flask test client.

        Args:
            flask_client: Flask app test_client()
        """
        self.client = flask_client

    def assert_status(self, response, expected_code):
        """Assert response status code matches expected.

        Args:
            response: Flask response object
            expected_code: Integer HTTP status code

        Returns:
            The response object for further assertions

        Raises:
            AssertionError if status code doesn't match
        """
        assert response.status_code == expected_code, (
            f"Expected status {expected_code}, got {response.status_code}. "
            f"Response: {response.data[:500]!r}"
        )
        return response

    def get_jobs(self, params=None):
        """GET /api/jobs with optional query parameters.

        Args:
            params: Optional dict of query parameters (e.g. {'qa': '1'})

        Returns:
            Flask response object
        """
        return self.client.get("/api/jobs", query_string=params)

    def get_saved_jobs(self):
        """GET /api/jobs/saved."""
        return self.client.get("/api/jobs/saved")

    def get_applied_jobs(self):
        """GET /api/jobs/applied."""
        return self.client.get("/api/jobs/applied")

    def get_stats(self):
        """GET /api/stats."""
        return self.client.get("/api/stats")

    def get_advanced_stats(self):
        """GET /api/stats/advanced."""
        return self.client.get("/api/stats/advanced")

    def save_job(self, job_id):
        """POST /api/jobs/<id>/save - toggle saved status.

        Args:
            job_id: Integer job ID

        Returns:
            Flask response object
        """
        return self.client.post(f"/api/jobs/{job_id}/save")

    def apply_job(self, job_id, status=None, cover_letter="", notes=""):
        """POST /api/jobs/<id>/apply - mark job as applied.

        Args:
            job_id: Integer job ID
            status: Pipeline status string (e.g. 'postulé', 'entretien')
            cover_letter: Optional cover letter text
            notes: Optional notes text

        Returns:
            Flask response object
        """
        data = {"cover_letter": cover_letter, "notes": notes}
        if status:
            data["status"] = status
        return self.client.post(
            f"/api/jobs/{job_id}/apply",
            data=json.dumps(data),
            content_type="application/json",
        )

    def update_notes(self, job_id, notes):
        """POST /api/jobs/<id>/notes - save notes for a job.

        Args:
            job_id: Integer job ID
            notes: Notes text string

        Returns:
            Flask response object
        """
        return self.client.post(
            f"/api/jobs/{job_id}/notes",
            data=json.dumps({"notes": notes}),
            content_type="application/json",
        )

    def update_pipeline(self, job_id, status):
        """POST /api/jobs/<id>/pipeline - update pipeline status.

        Args:
            job_id: Integer job ID
            status: Pipeline status string

        Returns:
            Flask response object
        """
        return self.client.post(
            f"/api/jobs/{job_id}/pipeline",
            data=json.dumps({"status": status}),
            content_type="application/json",
        )

    def enrich_job(self, job_id):
        """GET /api/jobs/enrich/<id> - trigger AI enrichment.

        Args:
            job_id: Integer job ID

        Returns:
            Flask response object
        """
        return self.client.get(f"/api/jobs/enrich/{job_id}")

    def get_index(self, params=None):
        """GET / (main page) with optional query parameters.

        Args:
            params: Optional dict of query parameters

        Returns:
            Flask response object
        """
        return self.client.get("/", query_string=params)

    def parse_json(self, response):
        """Parse JSON from a Flask response.

        Args:
            response: Flask response object

        Returns:
            Parsed Python dict/list
        """
        return json.loads(response.data.decode("utf-8"))

    def trigger_refresh(self):
        """GET /refresh - trigger manual scrape."""
        return self.client.get("/refresh")

    def api_trigger_refresh(self):
        """POST /api/refresh - API trigger scrape."""
        return self.client.post("/api/refresh")
