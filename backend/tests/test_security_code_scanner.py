"""Code security scanner tests.

Two themes run through this file. Most tests assert that a real weakness is
detected at the right line with the right severity. The rest assert the
negative: comments, test fixtures and already-safe calls must not produce
findings, because a scanner that cries wolf is one a team turns off.
"""

import pytest

from app.services import security_code_scanner as scanner
from app.services.security_code_scanner import CODE_RULES, is_code_path


def scan(path, content):
    return scanner.scan_content(path, content)


def rule_ids(matches) -> set[str]:
    return {match.rule_id for match in matches}


def only(path, content, rule_id):
    matches = [m for m in scan(path, content) if m.rule_id == rule_id]
    assert matches, f"expected {rule_id} in {rule_ids(scan(path, content))}"
    return matches[0]


class TestDetection:
    def test_sql_injection_via_fstring(self):
        match = only(
            "app/db.py",
            'cursor.execute(f"SELECT * FROM users WHERE id = {uid}")',
            "code.sql_injection.python",
        )
        assert match.severity == "high"
        assert match.category == "injection"
        assert match.line == 1

    def test_sql_injection_via_concatenation(self):
        assert "code.sql_injection.string_concat" in rule_ids(
            scan("app/db.py", 'sql = "SELECT * FROM t WHERE id = " + user_id')
        )

    def test_command_injection_via_shell(self):
        match = only(
            "app/run.py",
            'os.system("ls " + user_dir)',
            "code.command_injection",
        )
        assert match.severity == "critical"
        assert match.category == "injection"

    def test_command_injection_via_node_exec(self):
        assert "code.command_injection" in rule_ids(
            scan("app/run.js", 'child_process.exec("cat " + req.query.file)')
        )

    def test_subprocess_shell_true(self):
        match = only(
            "app/run.py",
            "subprocess.run(cmd, shell=True)",
            "code.command_injection.shell_true",
        )
        assert match.severity == "high"

    def test_eval(self):
        match = only("app/x.py", "result = eval(user_input)", "code.eval")
        assert match.severity == "high"
        assert match.category == "code_execution"

    def test_exec(self):
        assert "code.exec" in rule_ids(scan("app/x.py", "exec(payload)"))

    def test_java_runtime_exec(self):
        assert "code.java_runtime_exec" in rule_ids(
            scan("App.java", 'Runtime.getRuntime().exec(cmd);')
        )

    def test_path_traversal(self):
        assert "code.path_traversal" in rule_ids(
            scan("app/files.py", 'path = os.path.join(base, request.args["name"])')
        )

    def test_file_read_with_request_path(self):
        assert "code.read_file_join_input" in rule_ids(
            scan("app/files.py", 'data = open(os.path.join(dir, request.path))')
        )

    def test_weak_hash_md5(self):
        match = only("app/hash.py", "h = hashlib.md5(data)", "code.weak_hash_md5")
        assert match.severity == "medium"
        assert match.category == "crypto"

    def test_weak_hash_sha1(self):
        assert "code.weak_hash_sha1" in rule_ids(
            scan("app/hash.java", 'MessageDigest.getInstance("SHA-1")')
        )

    def test_weak_cipher_des(self):
        assert "code.weak_cipher_des" in rule_ids(
            scan("app/crypt.py", "cipher = DES.new(key, DES.MODE_ECB)")
        )

    def test_ecb_mode(self):
        assert "code.weak_cipher_ecb" in rule_ids(
            scan("app/crypt.py", "mode = MODE_ECB")
        )

    def test_insecure_random(self):
        assert "code.insecure_random" in rule_ids(
            scan("app/token.py", "value = random.randint(0, 100)")
        )

    def test_pickle_deserialization(self):
        match = only(
            "app/cache.py", "obj = pickle.loads(blob)", "code.insecure_deserialization.pickle"
        )
        assert match.severity == "high"
        assert match.category == "deserialization"

    def test_unsafe_yaml_load(self):
        assert "code.insecure_deserialization.yaml" in rule_ids(
            scan("app/conf.py", "cfg = yaml.load(text)")
        )

    def test_safe_yaml_load_is_not_reported(self):
        assert scan("app/conf.py", "cfg = yaml.load(text, Loader=yaml.SafeLoader)") == []

    def test_java_native_deserialization(self):
        assert "code.insecure_deserialization.java" in rule_ids(
            scan("App.java", "ObjectInputStream in = new ObjectInputStream(s);")
        )

    def test_node_deserialization(self):
        assert "code.insecure_deserialization.node" in rule_ids(
            scan("app/x.js", "const o = serialize.unserialize(input);")
        )

    def test_jwt_none_algorithm(self):
        match = only(
            "app/auth.py",
            "jwt.decode(token, options={'verify_signature': False})",
            "code.jwt_none_algorithm",
        )
        assert match.severity == "critical"
        assert match.category == "authentication"

    def test_jwt_verify_false_is_anchored_to_a_jwt_call(self):
        # A bare verify=False is almost always TLS, and is reported by the TLS
        # rule instead. The auth-bypass rule must not fire on it.
        assert "code.jwt_none_algorithm" not in rule_ids(
            scan("app/http.py", "requests.get(url, verify=False)")
        )
        assert "code.tls_verification_disabled" in rule_ids(
            scan("app/http.py", "requests.get(url, verify=False)")
        )

    def test_tls_verification_disabled_variants(self):
        for content in (
            "req = requests.get(url, verify=False)",
            "const agent = new https.Agent({rejectUnauthorized: false});",
            "conn.ssl_verify = false",
        ):
            assert "code.tls_verification_disabled" in rule_ids(scan("app/x.py", content))

    def test_debug_enabled(self):
        assert "code.debug_enabled" in rule_ids(scan("app.py", "DEBUG = True"))
        assert "code.debug_enabled" in rule_ids(
            scan("config.json", '{"debug": true}')
        )

    def test_client_side_injection_sink(self):
        assert "code.dangerous_function.javascript" in rule_ids(
            scan("app/x.js", "el.innerHTML = userInput;")
        )

    def test_cors_wildcard_origin(self):
        assert "code.cors_wildcard_origin" in rule_ids(
            scan("app/http.py", 'headers["Access-Control-Allow-Origin"] = "*"')
        )

    def test_hardcoded_credential_assignment(self):
        match = only(
            "app/settings.py",
            'PASSWORD = "s3cr3t-literal-value"',
            "code.hardcoded_credential_assignment",
        )
        assert match.severity == "high"

    def test_every_match_is_attributed_to_the_code_scanner(self):
        matches = scan("app/x.py", "eval(x)\nyaml.load(y)")
        assert matches
        assert all(m.scanner == "code" for m in matches)

    def test_line_numbers_are_one_based_and_accurate(self):
        content = "import os\n\n\nresult = eval(payload)\n"
        match = only("app/x.py", content, "code.eval")
        assert match.line == 4

    def test_multiple_findings_on_one_line_are_all_reported(self):
        content = "subprocess.run(cmd, shell=True); data = eval(x)"
        found = rule_ids(scan("app/x.py", content))
        assert "code.command_injection.shell_true" in found
        assert "code.eval" in found

    def test_the_same_rule_reports_once_per_line(self):
        matches = scan("app/x.py", "eval(a); eval(b); eval(c)")
        assert len([m for m in matches if m.rule_id == "code.eval"]) == 1


class TestFalsePositiveControl:
    def test_commented_python_is_not_a_finding(self):
        assert scan("app/x.py", "# eval(user_input)  # nosec") == []

    def test_commented_javascript_is_not_a_finding(self):
        assert scan("app/x.js", "// eval(userInput)") == []

    def test_literal_eval_is_not_eval(self):
        assert scan("app/x.py", "value = ast.literal_eval(text)") == []

    def test_test_files_are_skipped(self):
        assert scan("tests/test_x.py", "eval(payload)") == []
        assert scan("src/__tests__/x.test.ts", "eval(payload)") == []

    def test_example_paths_are_skipped(self):
        assert scan("examples/demo.py", "eval(payload)") == []

    def test_environment_sourced_credentials_are_not_findings(self):
        for content in (
            "password = os.environ['DB_PASSWORD']",
            "api_key = process.env.API_KEY",
            "secret = settings.SECRET_KEY",
        ):
            assert scan("app/settings.py", content) == []

    def test_md5_for_a_checksum_is_not_a_finding(self):
        assert scan("app/hash.py", "checksum = hashlib.md5(data)") == []

    def test_math_random_for_jitter_is_not_a_finding(self):
        assert scan("app/x.js", "const delay = Math.random() * 100;") == []

    def test_empty_input_yields_nothing(self):
        assert scan("app/x.py", "") == []
        assert scan("app/x.py", "\n\n   \n") == []

    def test_blank_path_yields_nothing(self):
        assert scan("", "eval(x)") == []

    def test_non_code_files_are_skipped(self):
        assert scan("assets/logo.png", "eval(x)") == []
        assert scan("data/rows.csv", "eval(x)") == []

    def test_safe_patterns_produce_no_findings(self):
        safe = "\n".join(
            [
                "import os",
                "import hashlib",
                "",
                "def handler(request):",
                "    cfg = yaml.safe_load(request.body)",
                "    digest = hashlib.sha256(cfg).hexdigest()",
                "    path = os.path.join(BASE, ALLOWED[id])",
                "    return subprocess.run([BIN, path], shell=False)",
            ]
        )
        assert scan("app/handler.py", safe) == []


class TestPathGating:
    @pytest.mark.parametrize(
        "path,expected",
        [
            ("app/main.py", True),
            ("src/index.ts", True),
            ("App.java", True),
            ("main.go", True),
            ("main.rb", True),
            ("index.php", True),
            ("lib.rs", True),
            ("script.sh", True),
            ("deploy.tf", True),
            ("config.yaml", True),
            ("Dockerfile", True),
            ("dockerfile.prod", True),
            ("Gemfile", True),
            ("notes.md", False),
            ("image.png", False),
            ("LICENSE", False),
        ],
    )
    def test_code_paths_are_recognised(self, path, expected):
        assert is_code_path(path) is expected


class TestRuleSet:
    def test_every_rule_has_a_unique_id(self):
        ids = [rule.rule_id for rule in CODE_RULES]
        assert len(ids) == len(set(ids))

    def test_every_rule_id_is_namespaced_to_the_code_scanner(self):
        for rule in CODE_RULES:
            assert rule.rule_id.startswith("code.")

    def test_every_rule_declares_a_supported_severity_and_category(self):
        from app.schemas.security import CATEGORIES, SEVERITIES

        for rule in CODE_RULES:
            assert rule.severity in SEVERITIES
            assert rule.category in CATEGORIES

    def test_confidence_is_within_range(self):
        for rule in CODE_RULES:
            assert 0.0 < rule.confidence <= 1.0

    def test_every_rule_carries_actionable_remediation(self):
        for rule in CODE_RULES:
            assert len(rule.remediation) > 20
            assert not rule.remediation.lower().startswith("consider")

    def test_scanner_reports_its_rule_catalogue(self):
        summary = scanner.rule_summary()
        assert len(summary) == len(CODE_RULES)
        assert {"rule_id", "title", "severity", "category"} <= set(summary[0])

    def test_supports_reports_rule_availability(self):
        instance = scanner.CodeScanner()
        assert instance.supports("code.eval")
        assert not instance.supports("secret.private_key")

    def test_a_custom_rule_set_is_honoured(self):
        import re as _re

        only_eval = scanner.CodeRule(
            rule_id="code.only_eval",
            title="eval",
            description="d",
            severity="high",
            category="code_execution",
            pattern=_re.compile(r"eval\("),
            confidence=0.9,
            remediation="r",
        )
        instance = scanner.CodeScanner(rules=(only_eval,))
        matches = instance.scan_text("a.py", "eval(x)\nyaml.load(y)")
        assert {m.rule_id for m in matches} == {"code.only_eval"}

    def test_a_rule_can_be_restricted_to_file_types(self):
        import re as _re

        js_only = scanner.CodeRule(
            rule_id="code.js_only",
            title="t",
            description="d",
            severity="low",
            category="misconfiguration",
            pattern=_re.compile(r"marker"),
            confidence=0.5,
            remediation="r",
            extensions=frozenset({".js"}),
        )
        instance = scanner.CodeScanner(rules=(js_only,))
        assert instance.scan_text("a.js", "marker") != []
        assert instance.scan_text("a.py", "marker") == []


class TestFindingPayload:
    def test_payload_carries_scanner_provenance_and_no_source_text(self):
        match = only("app/x.py", "result = eval(user_input)", "code.eval")
        payload = match.as_finding()
        assert payload["scanner"] == "code"
        assert payload["file"] == "app/x.py"
        assert payload["line"] == 1
        assert payload["remediation"]
        # The payload must not carry the matched source, which for a code rule
        # could contain a neighbouring credential.
        assert set(payload) <= {
            "file",
            "line",
            "column",
            "category",
            "severity",
            "confidence",
            "title",
            "description",
            "remediation",
            "scanner",
            "fingerprint",
        }

    def test_fingerprint_is_left_for_the_normalizer(self):
        # A code finding's identity is rule+path, not the matched text, so the
        # scanner must not invent one from the line contents.
        match = only("app/x.py", "result = eval(user_input)", "code.eval")
        assert match.as_finding().get("fingerprint", "") == ""

    def test_scan_lines_matches_scan_text(self):
        content = "eval(a)\nsubprocess.run(c, shell=True)"
        by_text = scanner.DEFAULT_CODE_SCANNER.scan_text("a.py", content)
        by_lines = scanner.DEFAULT_CODE_SCANNER.scan_lines("a.py", content.splitlines())
        assert [(m.rule_id, m.line) for m in by_lines] == [
            (m.rule_id, m.line) for m in by_text
        ]
