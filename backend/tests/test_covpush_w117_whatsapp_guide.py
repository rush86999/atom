"""Wave 117 coverage: integrations.whatsapp_api_setup_guide.

Covers the guide generator's executable functions (guide creation, environment
template, JSON serialization via main()) — mostly data, so structural contract
tests. ``main()`` writes to /tmp only; no network, no LLM.
"""

import json
import os

from integrations.whatsapp_api_setup_guide import (
    create_api_setup_guide,
    create_environment_template,
    main,
)

SETUP_FILES = [
    "/tmp/whatsapp_api_setup_guide.json",
    "/tmp/whatsapp_environment_template.json",
    "/tmp/whatsapp_environment_template.env",
]


class TestCreateApiSetupGuide:
    def test_guide_structure(self):
        guide = create_api_setup_guide()
        assert guide["title"] == "WhatsApp Business API Production Setup Guide"
        assert guide["estimated_time"] == "30 minutes"
        assert len(guide["prerequisites"]) == 4
        assert len(guide["step_by_step"]) == 8

    def test_guide_steps_have_titles_and_actions(self):
        guide = create_api_setup_guide()
        for step in guide["step_by_step"].values():
            assert step["title"]
            assert step["actions"]
            assert step["estimated_time"]

    def test_step_4_credentials(self):
        step = create_api_setup_guide()["step_by_step"]["step_4"]
        assert set(step["credentials"]) == {"access_token", "phone_number_id"}
        assert "EAAJZC" in step["credentials"]["access_token"]["format"]
        assert step["credentials"]["phone_number_id"]["format"] == "Numeric string"

    def test_step_5_webhook_events(self):
        step = create_api_setup_guide()["step_by_step"]["step_5"]
        assert "messages" in step["webhook_events"]
        assert "message_status" in step["webhook_events"]

    def test_step_7_environment_variables(self):
        step = create_api_setup_guide()["step_by_step"]["step_7"]
        expected = {
            "WHATSAPP_ACCESS_TOKEN_DEV",
            "WHATSAPP_PHONE_NUMBER_ID_DEV",
            "WHATSAPP_WEBHOOK_VERIFY_TOKEN_DEV",
            "WHATSAPP_WEBHOOK_URL_DEV",
        }
        assert expected.issubset(set(step["environment_variables"]))
        assert "5058" in step["environment_variables"]["WHATSAPP_WEBHOOK_URL_DEV"]

    def test_troubleshooting_has_four_issues(self):
        guide = create_api_setup_guide()
        assert len(guide["troubleshooting"]["common_issues"]) == 4
        for issue in guide["troubleshooting"]["common_issues"]:
            assert issue["issue"] and issue["solution"] and issue["check"]

    def test_production_checklist(self):
        guide = create_api_setup_guide()
        assert len(guide["production_checklist"]["before_going_live"]) == 8
        rate = guide["production_checklist"]["rate_limits"]
        assert rate["messages_per_second"] == "50"
        assert len(guide["production_checklist"]["security_requirements"]) == 5

    def test_resources_and_support(self):
        guide = create_api_setup_guide()
        assert "developers.facebook.com/docs/whatsapp" in guide["resources"]["official_documentation"]
        assert guide["support"]["atom_documentation"].endswith(".md")

    def test_serializable_to_json(self):
        json.dumps(create_api_setup_guide())  # must not raise


class TestCreateEnvironmentTemplate:
    def test_template_structure(self):
        template = create_environment_template()
        assert "Environment Variables Template" in template["description"]
        assert template["usage"].startswith("Copy these variables")

    def test_required_variables_present(self):
        variables = create_environment_template()["variables"]
        for key in [
            "WHATSAPP_ACCESS_TOKEN_DEV",
            "WHATSAPP_PHONE_NUMBER_ID_DEV",
            "WHATSAPP_BUSINESS_NAME",
            "DATABASE_HOST",
            "WHATSAPP_AUTO_REPLY_ENABLED",
            "WHATSAPP_RATE_LIMITING_ENABLED",
            "ENVIRONMENT",
        ]:
            assert key in variables

    def test_instructions_six_steps(self):
        instructions = create_environment_template()["instructions"]
        assert len(instructions) == 6
        assert instructions["step_1"].startswith("Copy the variables")

    def test_serializable_to_json(self):
        json.dumps(create_environment_template())


class TestMain:
    def test_main_writes_three_files(self, capsys):
        for path in SETUP_FILES:
            if os.path.exists(path):
                os.remove(path)

        main()

        assert os.path.exists(SETUP_FILES[0]), "setup guide JSON must be written"
        assert os.path.exists(SETUP_FILES[1]), "environment template JSON must be written"
        assert os.path.exists(SETUP_FILES[2]), ".env template must be written"

        with open(SETUP_FILES[0]) as f:
            guide = json.load(f)
        assert guide["estimated_time"] == "30 minutes"
        assert len(guide["step_by_step"]) == 8

        with open(SETUP_FILES[1]) as f:
            env_template = json.load(f)
        assert "WHATSAPP_ACCESS_TOKEN_DEV" in env_template["variables"]

        with open(SETUP_FILES[2]) as f:
            env_content = f.read()
        assert "WHATSAPP_ACCESS_TOKEN_DEV=EAAJZC" in env_content
        assert "ENVIRONMENT=development" in env_content

        out = capsys.readouterr().out
        assert "Setup Summary" in out
        assert "Total Steps: 8" in out
        assert "Configuration Files Created: 3" in out
        assert "Files Created:" in out
        assert "Quick Start:" in out
