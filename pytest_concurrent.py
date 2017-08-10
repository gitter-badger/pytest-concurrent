# -*- coding: utf-8 -*-
import re
import os
import py
import time
import multiprocessing
import concurrent.futures
import pytest
from _pytest.junitxml import LogXML
from _pytest.terminal import TerminalReporter
from _pytest.junitxml import Junit
from _pytest.junitxml import _NodeReporter
from _pytest.junitxml import bin_xml_escape
from _pytest.junitxml import mangle_test_address

### Manager for the shared variables being used by in multiprocess mode
MANAGER = multiprocessing.Manager()

### XMLSTATS is a shared variable used to override the local variable self.stats from LogXML
XMLSTATS = MANAGER.dict()
XMLSTATS['error'] = 0
XMLSTATS['passed'] = 0
XMLSTATS['failure'] = 0
XMLSTATS['skipped'] = 0
### XMLLOCK ensures that XMLSTATS is not being modified simultaneously
XMLLOCK = multiprocessing.Lock()

XMLREPORTER = MANAGER.dict()
# XMLREPORTER_ORDERED = MANAGER.list()
NODELOCK = multiprocessing.Lock()
NODEREPORTS = MANAGER.list()

### DICTIONARY is a shared variable used to keep track of the log for TerminalReporter
DICTIONARY = MANAGER.dict()
### STATS is a shared variable used to override the local variable self.stats from TerminalReporter
STATS = MANAGER.dict()
### LOCK ensures that STATS is not being modified simultaneously
LOCK = multiprocessing.Lock()

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

    nextitem = session.items[i+1] if i+1 < len(session.items) else None
    item.config.hook.pytest_runtest_protocol(item=item, nextitem=nextitem)
    if session.shouldstop:
        raise session.Interrupted(session.shouldstop)

@pytest.mark.trylast
def pytest_configure(config):
    # mode = session.config.option.concurrent_mode
    standard_reporter = config.pluginmanager.getplugin('terminalreporter')
    concurrent_reporter = ConcurrentTerminalReporter(standard_reporter)

    config.pluginmanager.unregister(standard_reporter)
    config.pluginmanager.register(concurrent_reporter, 'terminalreporter')

        if config.option.xmlpath is not None:
            xmlpath = config.option.xmlpath
            config.pluginmanager.unregister(config._xml)
            config._xml = ConcurrentLogXML(xmlpath, config.option.junitprefix, config.getini("junit_suite_name"))
            config.pluginmanager.register(config._xml)


### 
class ConcurrentNodeReporter(_NodeReporter):
    def __init__(self, nodeid, xml):

        self.id = nodeid
        self.xml = xml
        self.add_stats = self.xml.add_stats
        self.duration = 0
        self.properties = []
        self.nodes = []
        self.testcase = None
        self.attrs = {}

    def to_xml(self): ##overriden 
        testcase = Junit.testcase(time=self.duration, **self.attrs)
        print("TESTCASE:" + str(testcase) + " info = " + str(self.duration) + " " + str(self.attrs))
        testcase.append(self.make_properties_node())
        for node in self.nodes:
            testcase.append(node)
        return str(testcase.unicode(indent=0))

    def record_testreport(self, testreport):
        print("TEST: " + str(testreport))
        assert not self.testcase
        names = mangle_test_address(testreport.nodeid)
        classnames = names[:-1]
        if self.xml.prefix:
            classnames.insert(0, self.xml.prefix)
        attrs = {
            "classname": ".".join(classnames),
            "name": bin_xml_escape(names[-1]),
            "file": testreport.location[0],
        }
        if testreport.location[1] is not None:
            attrs["line"] = testreport.location[1]
        if hasattr(testreport, "url"):
            attrs["url"] = testreport.url
        self.attrs = attrs

    def finalize(self):
        data = self.to_xml() #.unicode(indent=0)
        self.__dict__.clear()
        self.to_xml = lambda: py.xml.raw(data)
        NODEREPORTS.append(data)

### ConcurrentLogXML is used to provide XML reporting for multiprocess mode
class ConcurrentLogXML(LogXML):

    def __init__(self, logfile, prefix, suite_name="pytest"):
        logfile = logfile
        logfile = os.path.expanduser(os.path.expandvars(logfile))
        self.logfile = os.path.normpath(os.path.abspath(logfile))
        self.prefix = prefix
        self.suite_name = suite_name
        self.stats = XMLSTATS
        self.node_reporters = {}#XMLREPORTER  # nodeid -> _NodeReporter
        self.node_reporters_ordered = []
        self.global_properties = []
        # List of reports that failed on call but teardown is pending.
        self.open_reports = []
        self.cnt_double_fail_tests = 0

    def pytest_sessionfinish(self):
        dirname = os.path.dirname(os.path.abspath(self.logfile))
        if not os.path.isdir(dirname):
            os.makedirs(dirname)
        logfile = open(self.logfile, 'w', encoding='utf-8')
        suite_stop_time = time.time()
        suite_time_delta = suite_stop_time - self.suite_start_time

        numtests = (self.stats['passed'] + self.stats['failure'] +
                    self.stats['skipped'] + self.stats['error'] -
                    self.cnt_double_fail_tests)
        print("NODE REPORTS: " + str(NODEREPORTS))
        logfile.write('<?xml version="1.0" encoding="utf-8"?>')
        logfile.write(Junit.testsuite(
            self._get_global_properties_node(),
            [concurrent_log_to_xml(x) for x in NODEREPORTS],
            name=self.suite_name,
            errors=self.stats['error'],
            failures=self.stats['failure'],
            skips=self.stats['skipped'],
            tests=numtests,
            time="%.3f" % suite_time_delta, ).unicode(indent=0))
        logfile.close()

    def add_stats(self, key):
        XMLLOCK.acquire()
        if key in self.stats:
            self.stats[key] += 1
        XMLLOCK.release()
    
    def node_reporter(self, report):
        nodeid = getattr(report, 'nodeid', report)
        # local hack to handle xdist report order
        slavenode = getattr(report, 'node', None)

        key = nodeid, slavenode
        # NODELOCK.acquire()
        if key in self.node_reporters:
            # TODO: breasks for --dist=each
            return self.node_reporters[key]

        reporter = ConcurrentNodeReporter(nodeid, self)

        self.node_reporters[key] = reporter
        # NODEREPORTS.append(reporter.to_xml())
        return reporter

    def pytest_terminal_summary(self, terminalreporter):
        terminalreporter.write_sep("-",
                                   "generated xml file: %s" % (self.logfile))
### ConcurrentTerminalReporter is used to provide terminal reporting for multiprocess mode
class ConcurrentTerminalReporter(TerminalReporter):
    def __init__(self, reporter):
        TerminalReporter.__init__(self, reporter.config)
        self._tw = reporter._tw
        self.stats = STATS

    def add_stats(self, key):
        if key in self.stats:
            self.stats[key] += 1

    def pytest_runtest_logreport(self, report):
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

def concurrent_log_to_xml(log):
    return py.xml.raw(log)
###----------------------------------------------------------------
