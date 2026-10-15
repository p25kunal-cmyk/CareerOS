"""Tests for CareerOS Local REST API.

Tests authentication, job management, application tracking,
pipeline stats, resume listing, and quick matching.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from src.api.server import create_app
from src.api.auth import (
    generate_api_token,
    verify_token,
    get_or_create_token,
)
from src.resume.models import BulletItem, SectionItem
from src.resume.repository import ResumeRepository


@pytest.fixture
def api_client(db):
    """Provide a TestClient connected to a test database."""
    app = create_app(db)
    return TestClient(app)


@pytest.fixture
def auth_headers():
    """Provide Authorization header with valid token."""
    token = get_or_create_token()
    return {"Authorization": f"Bearer {token}"}


class TestAuth:
    """Test API token generation, verification, and guards."""

    def test_generate_token_length(self):
        token = generate_api_token()
        assert len(token) == 64  # 32 bytes hex
        assert isinstance(token, str)

    def test_verify_token(self):
        token = generate_api_token()
        assert verify_token(token, token) is True
        assert verify_token("wrong-token", token) is False

    def test_health_check_unauthenticated(self, api_client):
        resp = api_client.get("/api/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"
        assert "uptime_seconds" in data

    def test_protected_route_missing_auth(self, api_client):
        resp = api_client.get("/api/jobs")
        assert resp.status_code == 401
        assert "Bearer token required" in resp.json()["detail"]

    def test_protected_route_invalid_token(self, api_client):
        resp = api_client.get(
            "/api/jobs",
            headers={"Authorization": "Bearer invalid_token_1234567890abcdef"},
        )
        assert resp.status_code == 401
        assert "Invalid API token" in resp.json()["detail"]

    def test_token_info_endpoint(self, api_client):
        resp = api_client.get("/api/token")
        assert resp.status_code == 200
        data = resp.json()
        assert "token" in data
        assert len(data["token"]) >= 32


class TestJobEndpoints:
    """Test job creation, retrieval, and listing."""

    def test_create_and_get_job(self, api_client, auth_headers):
        payload = {
            "title": "Product Manager",
            "company": "Google India",
            "location": "Bengaluru",
            "url": "https://careers.google.com/jobs/123",
            "source": "manual",
            "salary_raw": "₹30-40 LPA",
            "description": "Looking for an MBA PM to drive Search experiences.",
        }
        resp = api_client.post("/api/jobs", json=payload, headers=auth_headers)
        assert resp.status_code == 200
        job_data = resp.json()
        assert job_data["title"] == "Product Manager"
        assert job_data["company"] == "Google India"
        assert job_data["location"] == "Bengaluru"
        job_id = job_data["id"]

        # Fetch job by ID
        get_resp = api_client.get(f"/api/jobs/{job_id}", headers=auth_headers)
        assert get_resp.status_code == 200
        assert get_resp.json()["id"] == job_id

    def test_create_job_deduplication(self, api_client, auth_headers):
        payload = {
            "title": "Strategy Consultant",
            "company": "McKinsey",
            "location": "Mumbai",
            "description": "Consultant role for top tier graduates.",
        }
        # First creation
        resp1 = api_client.post("/api/jobs", json=payload, headers=auth_headers)
        assert resp1.status_code == 200
        id1 = resp1.json()["id"]

        # Second creation should return existing job
        resp2 = api_client.post("/api/jobs", json=payload, headers=auth_headers)
        assert resp2.status_code == 200
        id2 = resp2.json()["id"]
        assert id1 == id2

    def test_list_jobs_pagination(self, api_client, auth_headers):
        for i in range(5):
            api_client.post(
                "/api/jobs",
                json={"title": f"Analyst {i}", "company": f"Corp {i}"},
                headers=auth_headers,
            )

        resp = api_client.get("/api/jobs?limit=3&offset=0", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["jobs"]) == 3
        assert data["total"] >= 5

    def test_get_nonexistent_job_404(self, api_client, auth_headers):
        resp = api_client.get("/api/jobs/nonexistent-id", headers=auth_headers)
        assert resp.status_code == 404


class TestApplicationEndpoints:
    """Test job application workflow and status updates."""

    def test_apply_and_update_status(self, api_client, auth_headers):
        # 1. Create a job
        job_resp = api_client.post(
            "/api/jobs",
            json={"title": "Associate", "company": "Bain & Co"},
            headers=auth_headers,
        )
        job_id = job_resp.json()["id"]

        # 2. Apply
        apply_resp = api_client.post(
            f"/api/jobs/{job_id}/apply",
            json={"status": "applied", "notes": "Applied via referral"},
            headers=auth_headers,
        )
        assert apply_resp.status_code == 200
        app_data = apply_resp.json()
        assert app_data["status"] == "saved"
        assert app_data["job_id"] == job_id
        app_id = app_data["id"]

        # 3. Update status
        update_resp = api_client.put(
            f"/api/applications/{app_id}/status",
            json={"status": "interview", "note": "Round 1 scheduled"},
            headers=auth_headers,
        )
        assert update_resp.status_code == 200
        assert update_resp.json()["status"] == "interview"

        # 4. List applications
        list_resp = api_client.get("/api/applications", headers=auth_headers)
        assert list_resp.status_code == 200
        apps = list_resp.json()["applications"]
        assert any(a["id"] == app_id for a in apps)


class TestResumeAndStatsEndpoints:
    """Test resumes list, pipeline stats, and quick match."""

    def test_list_resumes_empty_and_populated(self, api_client, auth_headers, db):
        resp = api_client.get("/api/resumes", headers=auth_headers)
        assert resp.status_code == 200
        assert resp.json()["total"] == 0

        repo = ResumeRepository(db)
        repo.create_resume(name="My First Resume", is_master=True)

        resp2 = api_client.get("/api/resumes", headers=auth_headers)
        assert resp2.status_code == 200
        assert resp2.json()["total"] == 1
        assert resp2.json()["resumes"][0]["name"] == "My First Resume"

    def test_pipeline_stats(self, api_client, auth_headers):
        resp = api_client.get("/api/pipeline/stats", headers=auth_headers)
        assert resp.status_code == 200
        stats = resp.json()
        assert "total_applications" in stats
        assert "stages" in stats

    def test_quick_match(self, api_client, auth_headers, db):
        # 1. Create resume and version
        repo = ResumeRepository(db)
        r_id = repo.create_resume(name="MBA Placement Master", is_master=True)
        sec = SectionItem(
            section_type="experience",
            title="Professional Experience",
            bullets=[
                BulletItem(content="Led product strategy and roadmap for mobile app driving growth using Python and SQL"),
                BulletItem(content="Managed cross-functional Agile sprint teams"),
            ],
        )
        repo.create_version(resume_id=r_id, version_name="v1", sections=[sec])

        # 2. Create job
        job_resp = api_client.post(
            "/api/jobs",
            json={
                "title": "Lead Product Manager",
                "company": "TechCorp",
                "description": "Seeking Product Manager with Python, SQL, Agile skills.",
                "required_skills": ["Product Management", "Python", "SQL"],
            },
            headers=auth_headers,
        )
        job_id = job_resp.json()["id"]

        # 3. Match
        match_resp = api_client.post(
            "/api/match",
            json={"job_id": job_id, "resume_id": r_id},
            headers=auth_headers,
        )
        assert match_resp.status_code == 200
        data = match_resp.json()
        assert "overall_score" in data
        assert isinstance(data["matched_skills"], list)
        assert isinstance(data["missing_skills"], list)
