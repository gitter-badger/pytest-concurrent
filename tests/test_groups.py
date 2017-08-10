import time
import pytest


@pytest.mark.parametrize('mode', ['mthread', 'mproc'])
def test_concurrent_group(testdir, mode):
    """Make sure that pytest accepts our fixture."""

    # create a temporary pytest test module
    testdir.makepyfile("""
        import pytest
        import time

        @pytest.mark.concgroup(group=1)
        @pytest.mark.parametrize('para', [1,2,3,4,5])
        def test_something(para):
            time.sleep(2)
            _ = 1 / 0


        @pytest.mark.concgroup(1)
        def test_something_else():
            time.sleep(1)
            assert 1 == 2


        @pytest.mark.concgroup(group=2)
        @pytest.mark.parametrize('name', ['this', 'is', 'a', 'book'])
        def test_lots_of_things(name):
            time.sleep(2)


        def test_something_something_else():
            time.sleep(2)
            raise MemoryError
    """)

    before_run = time.time()
    # run pytest with the following cmd args
    result = testdir.runpytest(
        '--concmode=%s' % mode
    )
    after_run = time.time()

    # fnmatch_lines does an assertion internally
    result.stdout.fnmatch_lines([
        'test_concurrent_group.py:*: AssertionError',
        'test_concurrent_group.py:*: ZeroDivisionError',
        'test_concurrent_group.py:*: MemoryError'
    ])

    time_diff = after_run - before_run
    assert time_diff > 5 and time_diff < 8  # expected: 6
