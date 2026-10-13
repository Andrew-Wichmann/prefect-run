from prefect import flow


def job(fn=None, **flow_kwargs):
    """Wrap a function as a Prefect flow.

    Usable bare (``@job``) or with flow options (``@job(name="nightly")``).
    """

    def decorate(f):
        return flow(**flow_kwargs)(f)

    return decorate(fn) if fn is not None else decorate
