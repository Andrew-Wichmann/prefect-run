from prefect import flow, get_run_logger


@flow
def hello(name: str = "world"):
    get_run_logger().info(f"Hello, {name}!")
    return f"Hello, {name}!"
