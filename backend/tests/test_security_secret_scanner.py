"""Secret scanner tests.

The two properties under test throughout are the ones that matter most in this
module: a raw credential never leaves :meth:`SecretScanner.scan_text`, and a
credential duplicated across files is recognised as one leak rather than many.
"""

import pytest

from app.services import security_secret_scanner as scanner
from app.services.security_secret_scanner import (
    REDACTED,
    SecretRule,
    character_classes,
    fingerprint_for,
    looks_random,
    redact,
    shannon_entropy,
)

# A syntactically valid AWS key ID. AWS's own documentation key is used
# deliberately in one test below to prove placeholder suppression does not apply
# to prefix-anchored rules.
AWS_KEY = "AKIAIOSFODNN7EXAMPLE"
GITHUB_TOKEN = "ghp_TEST" + "a1B2c3D4e5F6g7H8i9J0k1L2m3N4o5P6q7R8"
SLACK_TOKEN = "xoxb-TEST-123456789012-abcdefghijklmnopFAKE"
GOOGLE_KEY = "AIzaTEST" + "SyD-1234567890abcdefghijklmnopqrstu"
JWT = (
    "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9"
    ".eyJzdWIiOiIxMjM0NTY3ODkwIiwibmFtZSI6IkpvaG4ifQ"
    ".SflKxwRJSMeKKF2QT4fwpMeJf36POk6yJV_adQssw5c"
)


def rule_ids(matches) -> set[str]:
    return {match.rule_id for match in matches}


def scan(path, content):
    return scanner.scan_content(path, content)


class TestRedaction:
    def test_redact_is_total(self):
        # A prefix-preserving mask would still leak entropy, and for a short
        # password most of the value. The mask keeps nothing.
        assert redact("hunter2") == REDACTED
        assert redact("sk_live_51H8xQ2") == REDACTED
        assert REDACTED not in ("", None)

    def test_match_never_carries_the_secret(self):
        match = scan("app/config.py", f'key = "{AWS_KEY}"')[0]
        assert match.redacted == REDACTED
        assert AWS_KEY not in match.redacted
        assert match.length == len(AWS_KEY)

    def test_finding_payload_contains_no_secret(self):
        match = scan("app/config.py", f'key = "{AWS_KEY}"')[0]
        payload = match.as_finding()
        rendered = repr(payload)
        assert AWS_KEY not in rendered
        assert REDACTED not in rendered  # not even the mask; the value is simply absent

    def test_fingerprint_is_stable_across_calls(self):
        first = scan("a.py", f'k = "{AWS_KEY}"')[0].fingerprint
        second = scan("a.py", f'k = "{AWS_KEY}"')[0].fingerprint
        assert first == second

    def test_fingerprint_differs_by_path(self):
        # The same key in two files is the same leak, but a *distinct* finding
        # per location, so the path is part of the identity.
        first = scan("a.py", f'k = "{AWS_KEY}"')[0].fingerprint
        second = scan("b.py", f'k = "{AWS_KEY}"')[0].fingerprint
        assert first != second

    def test_fingerprint_is_a_hash_not_the_value(self):
        digest = fingerprint_for("a.py", "secret.aws_access_key_id", REDACTED)
        assert len(digest) == 32
        assert AWS_KEY not in digest


class TestDetections:
    def test_aws_access_key_id(self):
        matches = scan("app/config.py", f'aws_key = "{AWS_KEY}"')
        assert "secret.aws_access_key_id" in rule_ids(matches)
        assert matches[0].severity == "critical"

    def test_aws_key_containing_the_word_example_is_still_reported(self):
        # Regression: the generic placeholder filter contains "example", and
        # AWS's documented example key contains it. A prefix-anchored rule must
        # not be suppressed by a heuristic meant for unanchored tokens.
        matches = scan("app/config.py", f'key = "{AWS_KEY}"')
        assert "secret.aws_access_key_id" in rule_ids(matches)

    def test_github_token(self):
        matches = scan("src/token.js", f'const t = "{GITHUB_TOKEN}";')
        assert "secret.github_token" in rule_ids(matches)
        assert matches[0].severity == "critical"

    def test_slack_token(self):
        assert "secret.slack_token" in rule_ids(
            scan("slack.py", f'token = "{SLACK_TOKEN}"')
        )

    def test_google_api_key(self):
        assert "secret.google_api_key" in rule_ids(
            scan("gcp.py", f'api_key = "{GOOGLE_KEY}"')
        )

    def test_jwt(self):
        matches = scan("auth.py", f'token = "{JWT}"')
        assert "secret.jwt" in rule_ids(matches)

    def test_private_key_block(self):
        content = (
            "-----BEGIN RSA PRIVATE KEY-----\n"
            "MIIEowIBAAKCAQEA\n"
            "-----END RSA PRIVATE KEY-----"
        )
        matches = scan("deploy/id_rsa", content)
        assert "secret.private_key" in rule_ids(matches)
        assert matches[0].severity == "critical"

    def test_database_uri_with_credentials(self):
        dsn = "postgres://admin:s3cr3tp4ss@db.internal:5432/app"
        matches = scan("app/db.py", f'url = "{dsn}"')
        assert "secret.database_uri" in rule_ids(matches)
        assert matches[0].severity == "critical"

    def test_credential_assignment(self):
        matches = scan("app/settings.py", 'password = "hunter2secret"')
        assert "secret.credential_assignment" in rule_ids(matches)

    def test_every_match_is_attributed_to_the_secret_scanner(self):
        matches = scan("app/config.py", f'k = "{AWS_KEY}"\npassword = "hunter2secret"')
        assert matches
        assert all(match.scanner == "secret" for match in matches)

    def test_line_number_points_at_the_match(self):
        content = "import os\n\n\nkey = \"%s\"\n" % AWS_KEY
        matches = scan("app/config.py", content)
        assert matches[0].line == 4

    def test_column_points_into_the_line(self):
        matches = scan("app/config.py", f'k = "{AWS_KEY}"')
        assert matches[0].column > 1


class TestFalsePositiveControl:
    @pytest.mark.parametrize(
        "content",
        [
            'password = os.environ["DB_PASSWORD"]',
            'api_key = process.env.API_KEY',
            'secret = settings.secret_key',
            'token = "${GITHUB_TOKEN}"',
            'password = "{{ vault_password }}"',
            "password = None",
        ],
    )
    def test_credentials_sourced_from_the_environment_are_not_findings(self, content):
        assert scan("app/settings.py", content) == []

    @pytest.mark.parametrize(
        "value",
        [
            "changeme",
            "your-api-key-here",
            "example-secret",
            "placeholder",
            "xxxxxxxx",
            "dummy-password",
        ],
    )
    def test_placeholder_values_are_suppressed_for_the_generic_rules(self, value):
        assert scan("app/settings.py", f'password = "{value}"') == []

    def test_database_uri_without_credentials_is_not_a_finding(self):
        dsn = "postgres://db.internal:5432/app"
        assert scan("app/db.py", f'url = "{dsn}"') == []

    def test_url_userinfo_is_not_double_reported_as_a_password(self):
        # The masked line must not also trip the generic credential rule.
        line = 'url = "https://user:s3cr3tpass@example.com/path"'
        matches = scan("app/http.py", line)
        assert all(m.rule_id != "secret.credential_assignment" for m in matches)

    def test_a_low_entropy_word_is_not_a_high_entropy_token(self):
        assert scan("app/x.py", f'value = "{GITHUB_TOKEN.replace(GITHUB_TOKEN[4:], "aaaaaaaaaaaaaaaaaaaaaaaa")}"') == []

    def test_env_example_file_placeholders_are_ignored(self):
        assert scan(".env.example", 'API_KEY=your-api-key-here') == []


class TestEntropy:
    def test_entropy_of_a_uniform_string_is_zero(self):
        assert shannon_entropy("aaaaaaaa") == pytest.approx(0.0)

    def test_entropy_of_an_empty_string_is_zero(self):
        assert shannon_entropy("") == 0.0

    def test_entropy_grows_with_distinct_characters(self):
        assert shannon_entropy("abcd") > shannon_entropy("aabb")

    def test_character_classes_are_counted(self):
        assert character_classes("abc") == 1
        assert character_classes("abcABC") == 2
        assert character_classes("abcABC123") == 3
        assert character_classes("abcABC123-_") == 4

    def test_looks_random_rejects_short_values(self):
        assert not looks_random("aB3$xY9")

    def test_looks_random_rejects_single_class_values(self):
        # A 40-character lowercase word is long but not random.
        assert not looks_random("a" * 40)

    def test_looks_random_accepts_a_token_shaped_value(self):
        assert looks_random("Xq7bR2vN9kL4mP8sT3wY6zA1cD5fH0jG")

    def test_looks_random_rejects_placeholders(self):
        assert not looks_random("your-api-key-placeholder-value")


class TestDedupe:
    def test_the_same_secret_repeated_in_one_file_is_one_finding(self):
        content = f'k1 = "{AWS_KEY}"\nk2 = "{AWS_KEY}"\nk3 = "{AWS_KEY}"'
        assert len(scan("app/config.py", content)) == 1

    def test_the_same_secret_in_two_files_is_two_findings(self):
        one = scan("a.py", f'k = "{AWS_KEY}"')
        two = scan("b.py", f'k = "{AWS_KEY}"')
        assert len(one) == 1 and len(two) == 1
        assert one[0].fingerprint != two[0].fingerprint

    def test_different_secrets_in_one_file_are_separate_findings(self):
        content = f'a = "{AWS_KEY}"\nb = "{GITHUB_TOKEN}"'
        assert len(scan("app/config.py", content)) == 2


class TestRuleSet:
    def test_every_rule_has_a_unique_id(self):
        ids = [rule.rule_id for rule in scanner.ALL_SECRET_RULES]
        assert len(ids) == len(set(ids))

    def test_every_rule_id_is_namespaced(self):
        for rule in scanner.ALL_SECRET_RULES:
            assert rule.rule_id.startswith("secret.")

    def test_every_rule_declares_a_supported_severity_and_category(self):
        from app.schemas.security import CATEGORIES, SEVERITIES

        for rule in scanner.ALL_SECRET_RULES:
            assert rule.severity in SEVERITIES
            assert rule.category in CATEGORIES

    def test_confidence_is_within_range(self):
        for rule in scanner.ALL_SECRET_RULES:
            assert 0.0 < rule.confidence <= 1.0

    def test_every_rule_has_actionable_remediation_text(self):
        # Supplied via as_finding, so check the emitted payloads.
        for rule in scanner.ALL_SECRET_RULES:
            payload = scanner.SecretMatch(
                rule_id=rule.rule_id,
                path="a.py",
                line=1,
                column=1,
                severity=rule.severity,
                category=rule.category,
                scanner="secret",
                title=rule.title,
                description=rule.description,
                redacted=REDACTED,
                length=10,
                fingerprint="f",
                confidence=rule.confidence,
            ).as_finding()
            assert payload["remediation"]
            assert "secret manager" in payload["remediation"].lower()

    def test_scanner_reports_its_supported_rules(self):
        summary = scanner.rule_summary()
        assert len(summary) == len(scanner.ALL_SECRET_RULES)
        assert {"rule_id", "title", "severity", "category"} <= set(summary[0])

    def test_supports_reports_rule_availability(self):
        instance = scanner.SecretScanner()
        assert instance.supports("secret.private_key")
        assert not instance.supports("code.sql_injection.python")

    def test_a_custom_rule_set_is_honoured(self):
        only_aws = SecretRule(
            rule_id="secret.only_aws",
            title="Only AWS",
            description="d",
            severity="critical",
            confidence=0.9,
            pattern=scanner.re.compile(r"AKIA[0-9A-Z]{16}"),
        )
        instance = scanner.SecretScanner(rules=(only_aws,))
        matches = instance.scan_text("a.py", f'k = "{GITHUB_TOKEN}"\nj = "{AWS_KEY}"')
        assert {match.rule_id for match in matches} == {"secret.only_aws"}


class TestEdgeCases:
    def test_empty_content_yields_nothing(self):
        assert scan("a.py", "") == []
        assert scan("a.py", "   \n\n  ") == []

    def test_blank_path_yields_nothing(self):
        assert scan("", f'k = "{AWS_KEY}"') == []

    def test_scan_lines_matches_scan_text(self):
        content = f'a = "{AWS_KEY}"\nb = "{GITHUB_TOKEN}"'
        by_text = scanner.DEFAULT_SECRET_SCANNER.scan_text("a.py", content)
        by_lines = scanner.DEFAULT_SECRET_SCANNER.scan_lines("a.py", content.splitlines())
        assert [m.fingerprint for m in by_lines] == [m.fingerprint for m in by_text]

    def test_binary_content_is_not_decoded(self):
        # The scan service screens binaries; the scanner itself is handed text.
        assert scan("a.py", "\x00\x01\x02") == []
