import json
import jsonpickle


def toJson(data):
    return json.dumps(json.loads(jsonpickle.encode(data)), indent=4, sort_keys=True)


def printObject(obj):
    print(toJson(obj))
