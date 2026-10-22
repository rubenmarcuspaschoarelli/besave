import sys
from pathlib import Path

TOOLS = Path(__file__).resolve().parent.parent
LOJAS = TOOLS / "capture-store-pages"
CHAT = TOOLS / "capture-chat-groups"

for p in (LOJAS, CHAT):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))
