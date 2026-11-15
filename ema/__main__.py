from .app import main

if __name__ == "__main__":  # the analyses' worker processes import this module again; only the first starts EMA
    main()
