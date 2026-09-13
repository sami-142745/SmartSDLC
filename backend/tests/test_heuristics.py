import pytest

from app.services.heuristics import run_heuristics


SAMPLE_PATCH = """\
@@ -5,6 +5,7 @@ def hello():
 def hello():
     pass
 
+    password = "hunter2"
+
 def world():
     pass"""


def test_run_heuristics_detects_hardcoded_credential():
    findings = run_heuristics(SAMPLE_PATCH, filename="config.py")
    assert len(findings) >= 1
    titles = [f["title"] for f in findings]
    assert any("Hardcoded credential" in t or "secret" in t.lower() for t in titles)
    finding = next(f for f in findings if "Hardcoded credential" in f["title"] or "credential" in f["title"].lower())
    assert finding["source"] == "heuristic"
    assert finding["category"] == "security"
    assert finding["severity"] == "low"


def test_run_heuristics_detects_embedded_key():
    patch = """\
@@ -1 +1,2 @@
+-----BEGIN RSA PRIVATE KEY-----
+MIIBogIBAAJBALRiMLAHudeSA/x3hB2f+2NRkJLA
"""
    findings = run_heuristics(patch, filename="key.pem")
    assert len(findings) >= 1
    assert any("secret key" in f["title"].lower() for f in findings)


def test_run_heuristics_returns_empty_for_clean_patch():
    patch = """\
@@ -1,3 +1,4 @@
 def greet(name):
-    return "hi"
+    greeting = f"hello {name}"
+    return greeting
"""
    findings = run_heuristics(patch, filename="greet.py")
    assert findings == []


def test_run_heuristics_returns_empty_for_empty_patch():
    assert run_heuristics("") == []
    assert run_heuristics("   ") == []


def test_run_heuristics_has_file_field():
    findings = run_heuristics(SAMPLE_PATCH, filename="app/main.py")
    assert all("file" in f for f in findings)


def test_run_heuristics_has_line_field():
    findings = run_heuristics(SAMPLE_PATCH, filename="app/main.py")
    for f in findings:
        assert "line" in f
        assert f["line"] is None or isinstance(f["line"], int)


def test_run_heuristics_deduplicates_identical_findings():
    finding = run_heuristics(SAMPLE_PATCH, filename="config.py")
    finding_2 = run_heuristics(SAMPLE_PATCH, filename="config.py")
    if finding:
        assert finding[0]["id"] == finding_2[0]["id"]


def test_run_heuristics_never_returns_critical_severity():
    findings = run_heuristics(SAMPLE_PATCH, filename="config.py")
    for f in findings:
        assert f["severity"] == "low"


def test_eval_in_comments_and_docstring_yields_single_finding():
    patch = """\
@@ -0,0 +1,9 @@
+\"\"\"
+Explanatory docstring:
+  1. eval() / arbitrary code execution from user-controlled input.
+  2. Calling eval() allows arbitrary code execution.
+\"\"\"
+def evaluate(data):
+    return eval(data)
+# NOTE: eval() over user input is dangerous
+def safe():
+    return 1
+"""
    findings = run_heuristics(patch, filename="vuln.py")
    exec_findings = [f for f in findings if f["title"] == "Dynamic code execution"]
    assert len(exec_findings) == 1
    assert exec_findings[0]["line"] == 7
    assert "eval(data)" in exec_findings[0]["code"]
    assert "safe parser" in exec_findings[0]["recommendation"].lower()


def test_sql_injection_fstring_is_detected():
    patch = """\
@@ -0,0 +1,2 @@
+def search(term):
+    return f"SELECT * FROM users WHERE name = '{term}'"
+"""
    findings = run_heuristics(patch, filename="db.py")
    sql_findings = [f for f in findings if f["title"] == "Possible SQL injection"]
    assert len(sql_findings) == 1
    assert sql_findings[0]["line"] == 2
    assert "parameterized" in sql_findings[0]["recommendation"].lower()


def test_api_secret_token_with_dashes_is_detected():
    patch = """\
@@ -0,0 +1,2 @@
+def get_key():
+    return "sk-fake-SmartsDLC-test-key-0123456789abcdef"  # noqa: S105
+"""
    findings = run_heuristics(patch, filename="keys.py")
    token_findings = [f for f in findings if "API secret token" in f["title"]]
    assert len(token_findings) == 1
    assert token_findings[0]["line"] == 2
    assert "secret manager" in token_findings[0]["recommendation"].lower()


def test_recommendations_match_vulnerability_category():
    patch = """\
@@ -0,0 +1,5 @@
+password = "hunter2"
+out = eval(data)
+query = f"SELECT * FROM users WHERE name = '{term}'"
+element.innerHTML = out
+return_value = pickle.loads(data)
+"""
    findings = run_heuristics(patch, filename="app.py")
    by_title = {f["title"]: f for f in findings}
    assert "Hardcoded credential" in by_title
    assert "secret manager" in by_title["Hardcoded credential"]["recommendation"].lower()
    assert "Dynamic code execution" in by_title
    assert "safe parser" in by_title["Dynamic code execution"]["recommendation"].lower()
    assert "Possible SQL injection" in by_title
    assert "parameterized" in by_title["Possible SQL injection"]["recommendation"].lower()
    assert "Client-side injection risk" in by_title
    assert "escape" in by_title["Client-side injection risk"]["recommendation"].lower()
    assert "Unsafe deserialization" in by_title
    assert "deserialization" in by_title["Unsafe deserialization"]["recommendation"].lower()


def test_full_line_comment_credential_produces_no_finding():
    patch = """\
@@ -0,0 +1,1 @@
+# password = "hunter2" (intentional test)
+"""
    findings = run_heuristics(patch, filename="config.py")
    assert findings == []


def test_assignment_inside_condition_is_detected():
    patch = """\
@@ -0,0 +1,4 @@
+def check(value):
+    if result = fetch(value):
+        return result
+    return None
+"""
    findings = run_heuristics(patch, filename="logic.py")
    bug_findings = [f for f in findings if f["title"] == "Assignment instead of comparison"]
    assert len(bug_findings) == 1
    assert bug_findings[0]["line"] == 2
    assert bug_findings[0]["category"] == "bug"
    assert "==" in bug_findings[0]["recommendation"]


def test_js_assignment_in_condition_is_detected():
    patch = """\
@@ -0,0 +1,1 @@
+if (x = y) {
+"""
    findings = run_heuristics(patch, filename="app.js")
    bug_findings = [f for f in findings if f["title"] == "Assignment instead of comparison"]
    assert len(bug_findings) == 1
    assert bug_findings[0]["line"] == 1
    assert bug_findings[0]["category"] == "bug"


def test_equality_comparison_is_not_flagged_as_assignment():
    patch = """\
@@ -0,0 +1,1 @@
+if result == other:
+"""
    findings = run_heuristics(patch, filename="logic.py")
    assert all(f["title"] != "Assignment instead of comparison" for f in findings)


def test_self_comparison_and_self_negation_are_detected():
    patch = """\
@@ -0,0 +1,2 @@
+if result == result:
+    return result != result
+"""
    findings = run_heuristics(patch, filename="logic.py")
    always_true = [f for f in findings if f["title"] == "Self-comparison (always true)"]
    always_false = [f for f in findings if f["title"] == "Self-negated comparison (always false)"]
    assert len(always_true) == 1
    assert always_true[0]["line"] == 1
    assert len(always_false) == 1
    assert always_false[0]["line"] == 2
    assert always_true[0]["category"] == "bug"


def test_pointless_self_assignment_is_detected():
    patch = """\
@@ -0,0 +1,1 @@
+    total = total
+"""
    findings = run_heuristics(patch, filename="math.py")
    bug_findings = [f for f in findings if f["title"] == "Pointless self-assignment"]
    assert len(bug_findings) == 1
    assert bug_findings[0]["line"] == 1
    assert bug_findings[0]["category"] == "bug"


def test_division_and_modulo_by_zero_are_detected():
    patch = """\
@@ -0,0 +1,2 @@
+ratio = total // 0
+remainder = balance % 0
+"""
    findings = run_heuristics(patch, filename="math.py")
    bug_findings = [f for f in findings if f["title"] == "Division or modulo by zero"]
    assert len(bug_findings) == 2
    assert {f["line"] for f in bug_findings} == {1, 2}
    assert bug_findings[0]["category"] == "bug"


def test_division_by_fraction_is_not_flagged_as_zero():
    patch = """\
@@ -0,0 +1,1 @@
+discount = total / 0.5
+"""
    findings = run_heuristics(patch, filename="math.py")
    assert all(f["title"] != "Division or modulo by zero" for f in findings)


def test_mutable_default_argument_is_detected():
    patch = """\
@@ -0,0 +1,1 @@
+def add_item(store, item, cache={}):
+"""
    findings = run_heuristics(patch, filename="store.py")
    bug_findings = [f for f in findings if f["title"] == "Mutable default argument"]
    assert len(bug_findings) == 1
    assert bug_findings[0]["line"] == 1
    assert "None as the default" in bug_findings[0]["recommendation"]
    assert bug_findings[0]["category"] == "bug"


def test_bare_except_is_detected_but_legit_except_is_not():
    patch = """\
@@ -0,0 +1,6 @@
+try:
+    run()
+except:
+    pass
+except ValueError:
+    pass
+"""
    findings = run_heuristics(patch, filename="app.py")
    bug_findings = [f for f in findings if f["title"] == "Broad exception silently swallowed"]
    assert len(bug_findings) == 1
    assert bug_findings[0]["line"] == 3
    assert bug_findings[0]["category"] == "bug"


def test_except_with_pass_on_same_line_is_detected():
    patch = """\
@@ -0,0 +1,1 @@
+except ValueError: pass
+"""
    findings = run_heuristics(patch, filename="app.py")
    bug_findings = [f for f in findings if f["title"] == "Broad exception silently swallowed"]
    assert len(bug_findings) == 1
    assert bug_findings[0]["line"] == 1


def test_shadowed_builtin_is_detected():
    patch = """\
@@ -0,0 +1,1 @@
+list = [1, 2, 3]
+"""
    findings = run_heuristics(patch, filename="views.py")
    bug_findings = [f for f in findings if f["title"] == "Variable shadows built-in name"]
    assert len(bug_findings) == 1
    assert bug_findings[0]["category"] == "bug"


def test_none_compared_with_equals_is_detected():
    patch = """\
@@ -0,0 +1,1 @@
+if value == None:
+"""
    findings = run_heuristics(patch, filename="config.py")
    bug_findings = [f for f in findings if f["title"] == "None compared with =="]
    assert len(bug_findings) == 1
    assert bug_findings[0]["line"] == 1
    assert "is None" in bug_findings[0]["recommendation"]


def test_boolean_identity_comparison_is_detected():
    patch = """\
@@ -0,0 +1,1 @@
+if running is True:
+"""
    findings = run_heuristics(patch, filename="service.py")
    bug_findings = [f for f in findings if f["title"] == "Identity comparison with boolean constant"]
    assert len(bug_findings) == 1
    assert bug_findings[0]["line"] == 1


def test_bug_hints_carry_format_shapes_identical_to_security():
    patch = """\
@@ -0,0 +1,3 @@
+if result == result:
+    password = "hunter2"
+    list = [1, 2, 3]
+"""
    findings = run_heuristics(patch, filename="app.py")
    assert len(findings) >= 3
    for f in findings:
        assert f["source"] == "heuristic"
        assert f["severity"] == "low"
        assert "recommendation" in f
        assert "heuristic_severity" in f
        assert "heuristic_confidence" in f
    by_title = {f["title"]: f for f in findings}
    assert by_title["Self-comparison (always true)"]["category"] == "bug"
    assert by_title["Hardcoded credential"]["category"] == "security"
    assert by_title["Variable shadows built-in name"]["category"] == "bug"


def test_comment_mentioning_same_eval_does_not_duplicate():
    patch = """\
@@ -0,0 +1,10 @@
+# eval() is called below
+# TODO: replace eval() with a parser
+def evaluate(data):
+    return eval(data)
+# end of block; eval() should only appear once as a finding
+def safe():
+    return 1
+"""
    findings = run_heuristics(patch, filename="vuln.py")
    exec_findings = [f for f in findings if f["title"] == "Dynamic code execution"]
    assert len(exec_findings) == 1
    assert exec_findings[0]["line"] == 4
