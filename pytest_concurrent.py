# -*- coding: utf-8 -*-

import multiprocessing
import concurrent.futures


def pytest_addoption(parser):
    group = parser.getgroup('concurrent')
    group.addoption(
        '--concurrent-mode',
        action='store',
        dest='concurrent_mode',
        default=None,
        help='Set the concurrent mode (multithread, multiprocess, asyncnetwork)'
    )
    group.addoption(
        '--concurrent-worker',
        action='store',
        dest='concurrent_workers',
        default=None,
        help='Set the concurrent worker amount (default to maximum)'
    )

    parser.addini('HELLO', 'Dummy pytest.ini setting')


def pytest_runtestloop(session):
    if (session.testsfailed and
            not session.config.option.continue_on_collection_errors):
        raise session.Interrupted(
            "%d errors during collection" % session.testsfailed)

    if session.config.option.collectonly:
        return True

    mode = session.config.option.concurrent_mode
    worker = None if session.config.option.concurrent_workers is None else int(session.config.option.concurrent_workers)

    # Achieve multi-thread using Python's threading library
    if mode == "multithread":
        with concurrent.futures.ThreadPoolExecutor(max_workers=worker) as executor:
            exec_items = list()
            for index, item in enumerate(session.items):
                exec_items.append(executor.submit(_run_next_item, session, item, index))
            for _ in concurrent.futures.as_completed(exec_items):
                pass

    # Multiprocess is not compatible with Windows !!!
    elif mode == "multiprocess":
        # with concurrent.futures.ProcessPoolExecutor(max_workers=worker) as executor:
        #     for index, item in enumerate(session.items):
        #         executor.submit(_run_next_item, session, item, index)
        procs_pool = dict()

        for index, item in enumerate(session.items):
            procs_pool[index] = multiprocessing.Process(target=_run_next_item, args=(session, item, index))
            procs_pool[index].start()

        for proc in procs_pool:
            procs_pool[proc].join()

    elif mode == "gevent":
        import gevent
        import gevent.pool
        import gevent.monkey
        gevent.monkey.patch_all()
        pool = gevent.pool.Pool(worker)
        for index, item in enumerate(session.items):
            pool.spawn(_run_next_item, session, item, index)
        pool.join()

    else:
        for i, item in enumerate(session.items):
            nextitem = session.items[i + 1] if i + 1 < len(session.items) else None
            item.config.hook.pytest_runtest_protocol(item=item, nextitem=nextitem)
            if session.shouldstop:
                raise session.Interrupted(session.shouldstop)
    return True


def _run_next_item(session, item, i):
    nextitem = session.items[i + 1] if i + 1 < len(session.items) else None
    item.config.hook.pytest_runtest_protocol(item=item, nextitem=nextitem)
    if session.shouldstop:
        raise session.Interrupted(session.shouldstop)
