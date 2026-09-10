from app.services.oauth_state import create_state, verify_state

SECRET = "test-secret"


def make_state(now: int = 1000, ttl: int = 600) -> str:
    return create_state(SECRET, ttl_seconds=ttl, now=now)


def test_valid_state_verifies():
    assert verify_state(make_state(), SECRET, now=1000)


def test_state_not_yet_expired_verifies():
    state = make_state(now=1000, ttl=600)
    assert verify_state(state, SECRET, now=1599)


def test_expired_state_is_rejected():
    state = make_state(now=1000, ttl=600)
    assert verify_state(state, SECRET, now=1601) is False


def test_tampered_signature_is_rejected():
    state = make_state()
    tampered = state[:-4] + ("abcd" if state[-4:] != "abcd" else "efgh")
    assert verify_state(tampered, SECRET, now=1000) is False


def test_wrong_secret_is_rejected():
    assert verify_state(make_state(), "other-secret", now=1000) is False


def test_tampered_nonce_is_rejected():
    state = make_state()
    nonce, expires, sig = state.split(".")
    tampered = f"X{nonce[1:]}.{expires}.{sig}"
    assert verify_state(tampered, SECRET, now=1000) is False


def test_empty_state_is_rejected():
    assert verify_state(None, SECRET, now=1000) is False
    assert verify_state("", SECRET, now=1000) is False


def test_malformed_state_is_rejected():
    assert verify_state("abc", SECRET, now=1000) is False


def test_non_numeric_expiry_is_rejected():
    assert verify_state("nonce.not.a.number.sig", SECRET, now=1000) is False