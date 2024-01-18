# Core Contact Plan Manager

A simple script to automatically configure wired links in core emu according to a plan file.

Example plan file:
```
# set looping of contact plan true/1 or false/0
s loop 0

# each entry starts with "a contact"
# a contact <begin timestamp in seconds> <end timestamp in seconds> <node id 1 OR node name> <node id 2 OR node name> <bandwidth> [loss%] [delay] [jitter]

a contact +0 +10 1 2 100000 0.2 0 0
a contact +10 +20 2 3 100000 0.2 0 0
```

The contact plan can also be looped if needed.
