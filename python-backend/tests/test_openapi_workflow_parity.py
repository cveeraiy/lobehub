from app.routers import openapi_message_translations, openapi_permissions, openapi_responses, openapi_roles, workflows
from app.services.workflows import temporal_backend
from app.services.workflows.handlers import WORKFLOW_HANDLERS


def _paths(router):
    return {(route.path, ",".join(sorted(route.methods or []))) for route in router.router.routes}


def test_openapi_rbac_routes_are_registered():
    permission_paths = _paths(openapi_permissions)
    role_paths = _paths(openapi_roles)

    assert ("/api/v1/permissions", "GET") in permission_paths
    assert ("/api/v1/permissions", "POST") in permission_paths
    assert ("/api/v1/permissions/{permission_id}", "DELETE") in permission_paths
    assert ("/api/v1/permissions/{permission_id}", "GET") in permission_paths
    assert ("/api/v1/permissions/{permission_id}", "PATCH") in permission_paths

    assert ("/api/v1/roles", "GET") in role_paths
    assert ("/api/v1/roles", "POST") in role_paths
    assert ("/api/v1/roles/{role_id}", "DELETE") in role_paths
    assert ("/api/v1/roles/{role_id}", "GET") in role_paths
    assert ("/api/v1/roles/{role_id}", "PATCH") in role_paths
    assert ("/api/v1/roles/{role_id}/permissions", "DELETE") in role_paths
    assert ("/api/v1/roles/{role_id}/permissions", "GET") in role_paths
    assert ("/api/v1/roles/{role_id}/permissions", "PATCH") in role_paths


def test_message_translation_routes_are_registered():
    paths = _paths(openapi_message_translations)

    assert ("/api/v1/message-translations/{message_id}", "DELETE") in paths
    assert ("/api/v1/message-translations/{message_id}", "GET") in paths
    assert ("/api/v1/message-translations/{message_id}", "PATCH") in paths
    assert ("/api/v1/message-translations/{message_id}", "POST") in paths


def test_workflow_routes_are_registered():
    paths = _paths(workflows)

    assert ("/api/workflows/task/heartbeat-tick", "POST") in paths
    assert ("/api/workflows/task/schedule-dispatch", "POST") in paths
    assert ("/api/workflows/task/schedule-execute", "POST") in paths
    assert ("/api/workflows/task/watchdog", "POST") in paths
    assert ("/api/workflows/agent-eval-run/run-benchmark", "POST") in paths
    assert ("/api/workflows/memory-user-memory/pipelines/chat-topic/process-topic", "POST") in paths


def test_responses_route_is_registered():
    paths = _paths(openapi_responses)

    assert ("/api/v1/responses", "POST") in paths


def test_temporal_workflow_dispatcher_covers_registered_routes():
    paths = {path for path, methods in _paths(workflows) if methods == "POST"}
    workflow_paths = {f"/api/workflows/{name}" for name in WORKFLOW_HANDLERS}

    assert paths <= workflow_paths


def test_temporal_workflow_id_is_stable_for_named_payload():
    workflow_id = temporal_backend.workflow_id_for("task/schedule-execute", {"taskId": "task:123"})

    assert workflow_id == "ethos-task-schedule-execute-task-123"
