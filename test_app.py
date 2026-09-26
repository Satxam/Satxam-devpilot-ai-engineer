import unittest
from unittest.mock import patch

import app


DEMO_ISSUES = [
    {"title": "Authentication bypass in login flow", "number": 1, "html_url": "issue/1", "state": "open", "body": "Users may bypass authentication."},
    {"title": "API returns 500 on malformed JSON", "number": 2, "html_url": "issue/2", "state": "open", "body": "The API returns an unhandled 500 response."},
    {"title": "Improve dashboard loading state", "number": 3, "html_url": "issue/3", "state": "open", "body": "Add a loading indicator."},
]


def github_result():
    return {"ok": True, "response": {"total_count": 3, "items": DEMO_ISSUES}}


class HermesRoutingTests(unittest.TestCase):
    def plan(self, request, tools):
        return {"token": "t", "repo": "Satxam/devpilot-demo", "jira_project": "KAN", "slack_channel": "#engineering",
                "request": request, "tools": tools, "reason": "Hermes plan", "needs_confirmation": False,
                "writes_require_confirmation": False}

    def test_informational_request_is_github_only(self):
        request = "Find the open issues in this repository."
        plan = self.plan(request, ["github"])
        with patch.object(app, "run_swytchcode", return_value=github_result()) as execute, patch.object(
            app, "hermes_decision", return_value={"intent": "report", "tools": [], "reason": "Informational request.", "needs_confirmation": False}
        ):
            result = app.run_plan(plan)
        self.assertEqual(result["plan"]["tools"], ["github"])
        self.assertEqual(execute.call_count, 1)

    def test_team_communication_request_is_github_then_slack(self):
        request = "Tell the engineering team about the critical issue."
        plan = self.plan(request, ["github", "slack"])
        with patch.object(app, "run_swytchcode", return_value=github_result()) as execute, patch.object(
            app, "hermes_decision", return_value={"intent": "notify", "tools": ["slack"], "reason": "User requested team communication.", "needs_confirmation": True}
        ):
            result = app.run_plan(plan)
        self.assertEqual(result["status"], "confirmation_required")
        self.assertEqual(result["plan"]["tools"], ["github", "slack"])
        self.assertEqual(execute.call_count, 1)

    def test_jira_request_is_github_then_jira(self):
        request = "Create Jira tickets for the critical issues."
        plan = self.plan(request, ["github", "jira"])
        with patch.object(app, "run_swytchcode", return_value=github_result()) as execute, patch.object(
            app, "hermes_decision", return_value={"intent": "track", "tools": ["jira"], "reason": "User requested Jira tracking.", "needs_confirmation": True}
        ):
            result = app.run_plan(plan)
        self.assertEqual(result["status"], "confirmation_required")
        self.assertEqual(result["plan"]["tools"], ["github", "jira"])
        self.assertEqual(execute.call_count, 1)

    def test_flagship_request_selects_both_and_executes_after_approval(self):
        request = "Find critical open bugs, create a Jira ticket for each critical bug, and notify the engineering team in Slack."
        plan = self.plan(request, ["github", "jira", "slack"])
        post = {"intent": "escalate", "tools": ["jira", "slack"], "reason": "Critical issue requires both requested actions.", "needs_confirmation": True}
        write_results = [{"ok": True, "response": {"key": "KAN-1"}}, {"ok": True, "response": {"ok": True}}]
        with patch.object(app, "run_swytchcode", side_effect=[github_result(), *write_results]) as execute, patch.object(app, "hermes_decision", return_value=post):
            pending = app.run_plan(plan, confirmed=False)
            final = app.run_plan(pending["plan"], confirmed=True)
        self.assertEqual(pending["status"], "confirmation_required")
        self.assertEqual(final["status"], "complete")
        self.assertEqual(execute.call_count, 3)
        self.assertIn("created 1 Jira ticket(s)", final["timeline"][-1]["detail"])
        self.assertIn("sent 1 Slack notification(s)", final["timeline"][-1]["detail"])

    def test_escalate_alone_does_not_infer_jira_or_slack(self):
        request = "Find critical open bugs and escalate them."
        plan = self.plan(request, ["github"])
        with patch.object(app, "run_swytchcode", return_value=github_result()), patch.object(
            app, "hermes_decision", return_value={"intent": "report", "tools": ["jira", "slack"], "reason": "Severity only.", "needs_confirmation": True}
        ):
            result = app.run_plan(plan)
        self.assertEqual(result["plan"]["tools"], ["github"])
        self.assertEqual(result["status"], "complete")

    def test_demo_severity_is_semantic_and_sorted_for_ui(self):
        analysis = app.summarize_github(github_result())
        self.assertEqual([i["severity"] for i in analysis["issues"]], ["CRITICAL", "HIGH", "NORMAL"])
        self.assertEqual(analysis["issues"][0]["title"], "Authentication bypass in login flow")
        self.assertEqual(analysis["issues"][1]["title"], "API returns 500 on malformed JSON")

    def test_empty_write_configuration_blocks_provider_calls(self):
        request = "Create Jira tickets for the critical issues and notify the engineering team in Slack."
        plan = self.plan(request, ["github", "jira", "slack"])
        plan["jira_project"] = ""
        plan["slack_channel"] = ""
        with patch.object(app, "run_swytchcode", return_value=github_result()) as execute, patch.object(
            app, "hermes_decision", return_value={"intent": "track and notify", "tools": ["jira", "slack"], "reason": "Requested.", "needs_confirmation": True}
        ):
            result = app.run_plan(plan, confirmed=True)
        self.assertEqual(result["status"], "configuration_error")
        self.assertEqual(execute.call_count, 1)
        self.assertEqual(result["actions"], {})

    def test_github_query_does_not_include_request(self):
        request = "Find the open issues in this repository and identify which ones need immediate attention."
        self.assertEqual(app.github_args("Satxam/devpilot-demo", request)["q"], "repo:Satxam/devpilot-demo is:issue is:open")
        self.assertNotIn(request, app.github_args("Satxam/devpilot-demo", request)["q"])

    def test_hermes_planning_is_strict_and_non_executing(self):
        with patch.object(app.subprocess, "run") as run:
            run.return_value = type("Completed", (), {"returncode": 0, "stdout": '{"intent":"find","tools":["github"],"reason":"Read issues.","needs_confirmation":false}', "stderr": ""})()
            decision = app.hermes_decision("Find open issues", "planning")
        self.assertEqual(decision["tools"], ["github"])
        self.assertIn("--safe-mode", run.call_args.args[0])
        self.assertNotIn("swytchcode", run.call_args.args[0])


if __name__ == "__main__":
    unittest.main()
