from prefect import task


def stage(fn=None, **task_kwargs):
    """Wrap a function as a Prefect task.

    Usable bare (``@stage``) or with task options (``@stage(retries=2)``).
    """

    def decorate(f):
        return task(**task_kwargs)(f)

    return decorate(fn) if fn is not None else decorate
