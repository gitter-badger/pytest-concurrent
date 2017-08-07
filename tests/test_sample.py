import time

def test_one():

    count = 0

    for num in range(99**3):
        count += 1
        
    time.sleep(1)
    assert count > 100000

def test_two():
    array = [2, 3, 4, 5, 6]
    time.sleep(1)
    assert array[1:4] == [3, 4, 5]

def test_three():
    name = "James"
    time.sleep(1)
    assert name == "James"

def test_four():
    name = "Reverb"
    time.sleep(1)
    assert name == "Reverb"

def test_five():
    val = 2 * 5 - 4
    time.sleep(1)
    assert val == 6

def test_six():
    val = 4
    for i in range(0, 1000):
        val = i
    time.sleep(1)
    assert val == 999

def test_seven():
    val = 4
    for i in range(0, 1000):
        val = i

    time.sleep(1)
    assert val == 999

# def test_eight():
#     fname = "Stephen"
#     lname = "Curry"
#     time.sleep(1)
#     assert fname + "_" + lname == "Stephen_Curry"

# def test_nine():
#     i = 100
#     result = 0
#     while i >= 2:
#         i = i / 2
#         result += 1
#     time.sleep(1)
#     assert result == 6

# def test_ten():
#     num = 169
#     div = 2

#     while num % div != 0:
#         div += 1
#     time.sleep(1)
#     assert div == 13

# def test_eleven():
#     i = 1
#     while i % 1000 != 0:
#         i += 1
#     time.sleep(1)
#     assert i == 1000

# def test_twelve():
#     i = 1
#     while i % 5000 != 0:
#         i += 1
#     time.sleep(1)
#     assert i == 5000

# def test_thirteen():
#     time.sleep(2)
#     name = "apple"
#     assert name == "apple"

# def test_fourteen():
#     time.sleep(1)
#     num = 2 * 2 * 2 * 2
#     assert num == 16

# def test_fifteen():
#     time.sleep(1)
#     num = 3 * 3 * 3
#     assert num == 27

# def test_sixteen():
#     time.sleep(1)
#     num = 5 * 5
#     assert num == 25
