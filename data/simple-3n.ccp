# set looping of contact plan true/1 or false/0
s loop 0

# each entry starts with "a contact"
# a contact <begin timestamp in seconds> <end timestamp in seconds> <node id 1> <node id 2> <bandwidth> [loss%] [delay] [jitter]

a contact +0 +10 1 2 100000 0.2 0 0
a contact +10 +20 2 3 100000 0.2 0 0
