import fcntl
import os

# fsync сейва; выставляется в ui/cli.py::prepare из [persistence] durable, в тестах выключен
DURABLE = True


def set_durable(flag: bool) -> None:
    global DURABLE
    DURABLE = flag


def sync_file(fd: int) -> None:
    # macOS: fsync не сбрасывает кэш диска, нужен F_FULLFSYNC; нет его или отказ -- обычный fsync
    full = getattr(fcntl, "F_FULLFSYNC", None)
    if full is not None:
        try:
            fcntl.fcntl(fd, full)
            return
        except OSError:
            pass
    os.fsync(fd)


def sync_dir(path) -> None:
    fd = os.open(path, os.O_RDONLY)
    try:
        sync_file(fd)
    finally:
        os.close(fd)
