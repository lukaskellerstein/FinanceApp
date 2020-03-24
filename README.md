
# Dev-Stack

Python

Poetry - package management

pandas

matplotlib

asyncio - asynchronous programming

Pygobject - GTK - as GUI

Gbulb - GTK + asyncio - Event loops

ib_insync - library for asynchronous communication with Interactive Brokers

rx - Reactive programming

pymongo - mongo database

black

flake8

rope


# Interactive brokers

App is using connection to the broker (http://interactivebrokers.github.io/tws-api/), so it is mandatory to have a account at Interactive Brokers.


# Bug

BUG in gbulb > glib_events.py > line 810

change from run_forever() -> run()

https://github.com/nhoad/gbulb/issues/19