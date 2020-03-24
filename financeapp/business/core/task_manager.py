import asyncio
from asyncio import Future

import gbulb

gbulb.install(gtk=True)
# loop = gbulb.get_event_loop()

loop = asyncio.get_event_loop()


class TaskManager:
    __instance = None

    tasks = {}

    @staticmethod
    def getInstance():
        """ Static access method. """
        if TaskManager.__instance == None:
            TaskManager()
        return TaskManager.__instance

    def __init__(self):
        """ Virtually private constructor. """
        if TaskManager.__instance != None:
            raise Exception("This class is a singleton!")
        else:
            TaskManager.__instance = self

    def run(self, key, future):
        print("task manager - run")
        task_instance = asyncio.run_coroutine_threadsafe(future, loop)
        self.__add(key, task_instance)

    def __add(self, key, value: Future):
        self.tasks[key] = value

    def exist(self, key):
        return key in self.tasks

    def close(self, key):

        aaa = self.tasks[key]

        print(aaa)
        print(type(aaa))

        self.tasks[key].cancel()
        self.tasks.pop(key)

        print(self.tasks)
