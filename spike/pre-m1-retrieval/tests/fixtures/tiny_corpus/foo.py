"""foo module docstring."""


def parse_config(path):
    """Parse a JSON config from disk."""
    import json
    with open(path) as f:
        return json.loads(f.read())


def main():
    cfg = parse_config("config.json")
    print(cfg)


if __name__ == "__main__":
    main()
