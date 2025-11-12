from app.security import hash_password, verify_password


def test_hash_and_verify_password_roundtrip():
    plaintext = "SuperSecret123!"
    hashed = hash_password(plaintext)

    assert hashed != plaintext
    assert verify_password(plaintext, hashed)


def test_verify_password_rejects_invalid():
    plaintext = "AnotherSecret!"
    hashed = hash_password(plaintext)

    assert not verify_password("WrongPassword", hashed)
    assert not verify_password(plaintext, "")

