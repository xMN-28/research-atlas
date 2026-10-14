"""Windows-friendly entry point; no package installation required."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / 'src'))
from literature_mining.pipeline import main

if __name__ == '__main__':
    main()
