import time
import pytest


@pytest.mark.concurrent_group(group=1)
def test_something():
    time.sleep(3)
    _ = 1 / 0


@pytest.mark.concurrent_group(1)
def test_something_else():
    time.sleep(5)
    assert 1 == 2


@pytest.mark.concurrent_group(group=2)
@pytest.mark.parametrize('name', ['this', 'is', 'a', 'book'])
def test_lots_of_things(name):
    time.sleep(2)


def test_something_something_else():
    time.sleep(5)
    assert 1 == 2
