from os.path import dirname, join

# Go up two levels: utils -> finance_app -> project root
MAIN_DIRECTORY = dirname(dirname(dirname(__file__)))


def get_full_path(*path):
    return join(MAIN_DIRECTORY, *path)
