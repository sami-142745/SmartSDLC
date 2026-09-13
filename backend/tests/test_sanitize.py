from app.services.sanitize import redact_secrets


def test_empty_input():
    assert redact_secrets("") == ""


def test_leaves_plain_code_alone():
    text = "const x = 1;\nfunction add(a, b) { return a + b; }\n"
    assert redact_secrets(text) == text


def test_redacts_private_key_block():
    text = (
        "-----BEGIN RSA PRIVATE KEY-----\n"
        "MIIEowIBAAKCAQEAunsecret\n"
        "-----END RSA PRIVATE KEY-----\nkeep"
    )
    out = redact_secrets(text)
    assert "[REDACTED]" in out
    assert "unsecret" not in out
    assert out.endswith("keep")


def test_redacts_github_token():
    out = redact_secrets("ghp_" + "a" * 36)
    assert out == "[REDACTED]"


def test_redacts_github_atom_token():
    out = redact_secrets("gho_" + "b" * 36)
    assert out == "[REDACTED]"


def test_redacts_gitlab_pat():
    out = redact_secrets("glpat-abcdefghijk0123456789")
    assert out == "[REDACTED]"


def test_redacts_aws_access_key():
    out = redact_secrets("AKIAIOSFODNN7EXAMPLE")
    assert out == "[REDACTED]"


def test_redacts_gcp_api_key():
    out = redact_secrets("AIzaSy" + "b" * 33)
    assert out == "[REDACTED]"


def test_redacts_generic_openai_key():
    out = redact_secrets("sk-proj-abcdef1234567890abcdef")
    assert out == "[REDACTED]"


def test_redacts_slack_token():
    out = redact_secrets("xoxb-1234567890-abcdefghij")
    assert out == "[REDACTED]"


def test_redacts_jwt():
    out = redact_secrets("eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiIxMjM0In0.abcdefghijklmnopqrstuvwxyz")
    assert out == "[REDACTED]"


def test_redacts_credential_assignment_equals():
    out = redact_secrets('password = "hunter2secretvalue"')
    assert out == 'password = [REDACTED]'


def test_redacts_credential_assignment_colon():
    out = redact_secrets("API_KEY: 'supersecretvalue123'")
    assert out == "API_KEY: [REDACTED]"


def test_redacts_multiple_secrets_in_one_buffer():
    text = "token=ghp_" + "c" * 36 + "\nclient_secret=\"keepmehidden123456\""
    out = redact_secrets(text)
    assert "REDACTED" in out
    assert "keepmehidden" not in out