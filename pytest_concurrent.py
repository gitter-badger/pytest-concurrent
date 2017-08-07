# -*- coding: utf-8 -*-

import multiprocessing
import concurrent.futures
import pytest
from _pytest.terminal import TerminalReporter
from _pytest.junitxml import LogXML
from _pytest.junitxml import _NodeReporter

MANAGER = multiprocessing.Manager()
DICTIONARY = MANAGER.dict()
STATS = MANAGER.dict()
LOCK = multiprocessing.Lock()
NODE_REPORTERS = MANAGER.dict()

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
    ### Use the variable to modify the mode of execution, avaliable options = multithread, multiprocess, async, sequential

    if (session.testsfailed and
            not session.config.option.continue_on_collection_errors):
        raise session.Interrupted(
            "%d errors during collection" % session.testsfailed)

    if session.config.option.collectonly:
        return True

    mode = session.config.option.concurrent_mode
    worker = None if session.config.option.concurrent_workers is None else int(session.config.option.concurrent_workers)
    ### Multiprocess is not compatible with Windows !!! ###
    if mode == "multiprocess":
        procs_pool = dict()

        for index, item in enumerate(session.items):
            procs_pool[index] = multiprocessing.Process(target=_run_next_item, args=(session, item, index))
            procs_pool[index].start()

        for proc in procs_pool:
            procs_pool[proc].join()

    ## Achieve async using Python's concurrent library ###
    elif mode == "multithread":
        with concurrent.futures.ThreadPoolExecutor(max_workers=8) as executor:
            for index, item in enumerate(session.items):
                executor.submit(_run_next_item, session, item, index)

    elif mode == "gevent":
        import gevent.monkey
        import gevent.pool
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
    # thread_name = "Thread " + str(i)
    # print("%s: %s" % (thread_name, time.ctime(time.time())))
    nextitem = session.items[i+1] if i+1 < len(session.items) else None
    item.config.hook.pytest_runtest_protocol(item=item, nextitem=nextitem)
    # print(str(i) + " " + str(item))
    if session.shouldstop:
        raise session.Interrupted(session.shouldstop)

@pytest.mark.trylast
def pytest_configure(config):
    # mode = session.config.option.concurrent_mode
    standard_reporter = config.pluginmanager.getplugin('terminalreporter')
    concurrent_reporter = ConcurrentTerminalReporter(standard_reporter)

    config.pluginmanager.unregister(standard_reporter)
    config.pluginmanager.register(concurrent_reporter, 'terminalreporter')

    # xmlpath = config.option.xmlpath
    # standard_logger = config.pluginmanager.getplugin(config._xml)
    # concurrent_logger = NewLogXML(xmlpath, config.option.junitprefix, config.getini("junit_suite_name"))
    # config.pluginmanager.register(concurrent_logger, config._xml)

class _ConcurrentNodeReporter(_NodeReporter):
    def __init__(self, nodeid, xml):

        self.id = nodeid
        self.xml = xml
        self.add_stats = self.xml.add_stats
        self.duration = 0
        self.properties = []
        self.nodes = []
        self.testcase = None
        self.attrs = {}

    def append(self, node):
        self.xml.add_stats(type(node).__name__)
        self.nodes.append(node)

# class NewLogXML(LogXML):
#     def __init__(self, logfile, prefix, suite_name="pytest"):
#         logfile = os.path.expanduser(os.path.expandvars(logfile))
#         self.logfile = os.path.normpath(os.path.abspath(logfile))
#         self.prefix = prefix
#         self.suite_name = suite_name
#         self.stats = dict.fromkeys([
#             'error',
#             'passed',
#             'failure',
#             'skipped',
#         ], 0)
#         self.node_reporters = NODE_REPORTERS  # nodeid -> _NodeReporter
#         self.node_reporters_ordered = []
#         self.global_properties = []
#         # List of reports that failed on call but teardown is pending.
#         self.open_reports = []
#         self.cnt_double_fail_tests = 0

    # def pytest_runtest_logreport(self, report):
    #     close_report = None
    #     if report.passed:
    #         if report.when == "call":  # ignore setup/teardown
    #             reporter = self._opentestcase(report)
    #             reporter.append_pass(report)
    #     elif report.failed:
    #         if report.when == "teardown":
    #             # The following vars are needed when xdist plugin is used
    #             report_wid = getattr(report, "worker_id", None)
    #             report_ii = getattr(report, "item_index", None)
    #             close_report = next(
    #                 (rep for rep in self.open_reports
    #                  if (rep.nodeid == report.nodeid and
    #                      getattr(rep, "item_index", None) == report_ii and
    #                      getattr(rep, "worker_id", None) == report_wid)), None)
    #             if close_report:
    #                 # We need to open new testcase in case we have failure in
    #                 # call and error in teardown in order to follow junit
    #                 # schema
    #                 self.finalize(close_report)
    #                 self.cnt_double_fail_tests += 1
    #         reporter = self._opentestcase(report)
    #         if report.when == "call":
    #             reporter.append_failure(report)
    #             self.open_reports.append(report)
    #         else:
    #             reporter.append_error(report)
    #     elif report.skipped:
    #         reporter = self._opentestcase(report)
    #         reporter.append_skipped(report)
    #     self.update_testcase_duration(report)
    #     if report.when == "teardown":
    #         reporter = self._opentestcase(report)
    #         reporter.write_captured_output(report)
    #         self.finalize(report)
    #         report_wid = getattr(report, "worker_id", None)
    #         report_ii = getattr(report, "item_index", None)
    #         close_report = next(
    #             (rep for rep in self.open_reports
    #              if (rep.nodeid == report.nodeid and
    #                  getattr(rep, "item_index", None) == report_ii and
    #                  getattr(rep, "worker_id", None) == report_wid)), None)
    #         if close_report:
    #             self.open_reports.remove(close_report)

class ConcurrentTerminalReporter(TerminalReporter):
    def __init__(self, reporter):
        TerminalReporter.__init__(self, reporter.config)
        self._tw = reporter._tw
        self.stats = STATS

    # def pytest_collectreport(self, report):
    #     # Show errors occurred during the collection instantly.
    #     TerminalReporter.pytest_collectreport(self, report)
    #     if report.failed:
    #         if self.isatty:
    #             self.rewrite('')  # erase the "collecting"/"collected" message
    #         self.print_failure(report)
    # def pytest_runtest_logstart(self, nodeid, location):
    #     if self.showlongtestinfo:
    #         line = self._locationline(nodeid, *location)
    #         self.write_ensure_prefix(line, "")
    #     elif self.showfspath:
    #         fsid = nodeid.split("::")[0]
    #         self.write_fspath_result(fsid, "")

    def pytest_runtest_logreport(self, report):
        # Show failures and errors occuring during running a test
        # instantly.
        # TerminalReporter.pytest_runtest_logreport(self, report)
        rep = report
        res = self.config.hook.pytest_report_teststatus(report=rep)
        cat, letter, word = res

        append_list(self.stats, cat, rep)

        if report.when == 'call':
            DICTIONARY[report.nodeid] = report
        self._tests_ran = True
        if not letter and not word:
            # probably passed setup/teardown
            return
        if self.verbosity <= 0:
            if not hasattr(rep, 'node') and self.showfspath:
                self.write_fspath_result(rep.nodeid, letter)
            else:
                self._tw.write(letter)
        else:
            if isinstance(word, tuple):
                word, markup = word
            else:
                if rep.passed:
                    markup = {'green': True}
                elif rep.failed:
                    markup = {'red': True}
                elif rep.skipped:
                    markup = {'yellow': True}
            line = self._locationline(rep.nodeid, *rep.location)
            if not hasattr(rep, 'node'):
                self.write_ensure_prefix(line, word, **markup)
                # self._tw.write(word, **markup)
            else:
                self.ensure_newline()
                if hasattr(rep, 'node'):
                    self._tw.write("[%s] " % rep.node.gateway.id)
                self._tw.write(word, **markup)
                self._tw.write(" " + line)
                self.currentfspath = -2

def append_list(stats, cat, rep):
    LOCK.acquire()
    cat_string = str(cat)
    if stats.get(cat_string) is None:
        stats[cat_string] = MANAGER.list()

    mylist = stats.get(cat_string)
    mylist.append(rep)
    stats[cat] = mylist
    LOCK.release()
