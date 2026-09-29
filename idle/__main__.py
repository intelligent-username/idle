"""Entry point shim."""


def main() -> None:
    """Launch CLI with lazy imports."""
    from idle.cli import main as cli_main

    cli_main()


if __name__ == "__main__":
    main()
