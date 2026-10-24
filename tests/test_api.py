from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_health_check():
    response = client.get('/health')
    assert response.status_code == 200
    assert response.json()['status'] == 'ok'


def test_create_job_rejects_missing_domain():
    response = client.post('/jobs', json={})
    assert response.status_code == 422


def test_create_job_returns_queued_status():
    response = client.post('/jobs', json={'domain': 'https://example.com', 'max_pages': 10})
    assert response.status_code == 202
    result = response.json()
    assert result['domain'] == 'https://example.com'
    assert result['status'] == 'queued'
    assert result['max_pages'] == 10
    assert result['seo_score'] is None


def test_create_project_rejects_private_url():
    response = client.post('/api/projects', json={'name': 'Local', 'start_url': 'http://127.0.0.1'})
    assert response.status_code == 400


def test_create_project_and_start_crawl():
    project_response = client.post(
        '/api/projects',
        json={'name': 'Example', 'start_url': 'https://example.com'},
    )
    assert project_response.status_code == 201
    project = project_response.json()
    assert project['domain'] == 'example.com'

    crawl_response = client.post(f"/api/projects/{project['id']}/crawl")
    assert crawl_response.status_code == 202
    assert crawl_response.json()['status'] == 'QUEUED'

    export_response = client.get(f"/api/projects/{project['id']}/export/json")
    assert export_response.status_code == 200
    assert export_response.json()['project']['name'] == 'Example'
