import string

from app.utils import generate_temp_password


def test_generate_temp_password_default_length():
    assert len(generate_temp_password()) == 12


def test_generate_temp_password_custom_length():
    assert len(generate_temp_password(20)) == 20


def test_generate_temp_password_alphanumeric_only():
    allowed = set(string.ascii_letters + string.digits)
    for _ in range(50):
        assert set(generate_temp_password()).issubset(allowed)


def test_generate_temp_password_is_random():
    passwords = {generate_temp_password() for _ in range(10)}
    assert len(passwords) > 1
