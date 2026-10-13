from hello import hello

if __name__ == "__main__":
    hello.from_source(
        source="/opt/flows",
        entrypoint="hello.py:hello",
    ).deploy(
        name="hello-local",
        work_pool_name="local-pool",
        parameters={"name": "world"},
    )
