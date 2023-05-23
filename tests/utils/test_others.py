import pytest


def test_tostr():
    from git_fat.utils import tostr

    bytest_to_str = tostr(b"fat content")
    assert isinstance(bytest_to_str, str)
    str_to_str = tostr("fat content")
    assert isinstance(str_to_str, str)

    with pytest.raises(ValueError):
        tostr(1)
