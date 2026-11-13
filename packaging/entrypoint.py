"""PyInstaller entry point using an absolute package import."""

from book_my_date.app import main

if __name__ == "__main__":
    raise SystemExit(main())
