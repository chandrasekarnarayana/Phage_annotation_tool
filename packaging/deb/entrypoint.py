"""PyInstaller entry point. Delegates straight to the real CLI."""

from phage_annotator.cli import main

if __name__ == "__main__":
    main()
