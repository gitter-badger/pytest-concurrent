import requests


def test_something():
    print('test_something starts')
    requests.get('http://localhost:8080/sleep/4')
    print('test_something finishes')


def test_something_else():
    print('test_something_else starts')
    requests.get('http://localhost:8080/sleep/4')
    # assert 1 == 2
    print('test_something_else finishes')
