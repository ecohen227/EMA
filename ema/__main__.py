if __name__ == "__main__":  # the analyses' worker processes import this module again: only the first starts EMA (and Qt)
    from .app import main

    main()
