import hashlib

from app.agents.builtin import BUILTIN_AGENT_SLUGS, get_builtin_agent_definition
from app.skills.builtin import BUILTIN_SKILLS, get_builtin_skill


def _sha256(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


def test_builtin_skill_catalog_contains_expected_entries_and_resources():
    identifiers = {skill["identifier"] for skill in BUILTIN_SKILLS}

    assert identifiers == {"lobe-agent-browser", "lobe-artifacts", "lobehub", "task"}

    agent_browser = get_builtin_skill("lobe-agent-browser")
    assert agent_browser is not None
    assert _sha256(agent_browser["content"]) == (
        "74363f11eb557e644607e114210f90a67c92c83f41ab5741f26e723748344775"
    )

    artifacts = get_builtin_skill("lobe-artifacts")
    assert artifacts is not None
    assert _sha256(artifacts["content"]) == (
        "1f311ef4cba4ef97f4b025b246995ce1a30d2a33061e022bdaa5fde06dc6cdfc"
    )

    lobehub = get_builtin_skill("lobehub")
    assert lobehub is not None
    assert lobehub["source"] == "builtin"
    assert "{{agent_id}}" in lobehub["content"]
    assert _sha256(lobehub["content"]) == (
        "072da2afc097533f6ffe0c9397153f3ee982c73386282c96e3b3a7b9e350f9ef"
    )
    assert set(lobehub["resources"]) == {
        "references/agent",
        "references/bot",
        "references/bot/discord",
        "references/bot/feishu",
        "references/bot/lark",
        "references/bot/qq",
        "references/bot/slack",
        "references/bot/telegram",
        "references/bot/wechat",
        "references/config",
        "references/doc",
        "references/eval",
        "references/file",
        "references/generate",
        "references/kb",
        "references/memory",
        "references/message",
        "references/model",
        "references/plugin",
        "references/provider",
        "references/search",
        "references/skill",
        "references/topic",
    }
    assert _sha256(lobehub["resources"]["references/bot/discord"]["content"]) == (
        "d2a982168d78d2eccacc492f0a04ad8ca2a2c00fc4cd4a0c7a884dcaecc58b0c"
    )
    assert _sha256(lobehub["resources"]["references/generate"]["content"]) == (
        "696f36ed09f865d321af97f3771ef48fc667cc605551b0fb6faa26e639bf6a8d"
    )

    task = get_builtin_skill("Task")
    assert task is not None
    assert task["identifier"] == "task"
    assert _sha256(task["content"]) == (
        "645c6fab76ed14eb0cc3771737030d7449708a9e63e7622a9d438582e2701f43"
    )
    assert "references/commands" in task["resources"]
    assert _sha256(task["resources"]["references/commands"]["content"]) == (
        "a1b7ccca9a48691ff6d1db42f26ae1b57c0d43675713cc9ff4b8dbdaa6da8d5b"
    )


def test_builtin_agent_catalog_contains_full_runtime_prompt_markers():
    slugs = set(BUILTIN_AGENT_SLUGS.values())

    assert slugs == {
        "agent-builder",
        "group-agent-builder",
        "group-supervisor",
        "inbox",
        "page-agent",
        "task-agent",
        "web-onboarding",
    }

    agent_builder = get_builtin_agent_definition("agent-builder")
    assert agent_builder is not None
    assert "getAvailableModels" in agent_builder["runtime"]["systemRole"]
    assert agent_builder["runtime"]["plugins"] == ["lobe-agent-builder"]

    group_builder = get_builtin_agent_definition("group-agent-builder")
    assert group_builder is not None
    assert "<prompt_architecture>" in group_builder["runtime"]["systemRole"]
    assert "lobe-group-agent-builder" in group_builder["runtime"]["plugins"]

    onboarding = get_builtin_agent_definition("web-onboarding", {"userLocale": "en-US"})
    assert onboarding is not None
    system_role = onboarding["runtime"]["systemRole"]
    assert "Pre-Finish Checklist" in system_role
    assert "showAgentMarketplace exactly once" in system_role
    assert "Preferred reply language: en-US. This is mandatory." in system_role
    assert onboarding["persist"] == {"model": "gpt-4o-mini", "provider": "openai"}
