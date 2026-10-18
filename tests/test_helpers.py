import pytest

from tests.helpers import assert_safe_test_database


def test_guard_accepts_test_database():
    assert_safe_test_database('postgresql://u:p@localhost:5433/craig_test')


@pytest.mark.parametrize('url', [
    'postgresql://u:p@localhost:5432/craigbot',
    'postgresql://u:p@localhost:5432/',
])
def test_guard_refuses_other_databases(url):
    with pytest.raises(RuntimeError, match='Refusing'):
        assert_safe_test_database(url)
