"""Drop Prometheus files for Gunicorn workers that have exited."""

from prometheus_client import multiprocess


def child_exit(_server, worker):
    multiprocess.mark_process_dead(worker.pid)
