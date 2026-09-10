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
