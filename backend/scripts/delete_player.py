"""
Delete a REAL player completely: database row, jobs, uploads, converted and annotated videos.
Stop the server first (it keeps players in memory), then:

    python backend/scripts/delete_player.py p_001
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from backend.app import config, db  # noqa: E402


def main(pid):
    rec = next((r for r in db.load_players() if r["id"] == pid), None)
    if rec is None:
        sys.exit(f"{pid} is not a real player in {config.DB_PATH}")
    removed = []
    for folder in (config.UPLOAD_DIR, config.WORK_DIR, config.MEDIA_DIR):
        for f in folder.glob(f"{pid}_*"):
            f.unlink()
            removed.append(f.name)
    db.delete_player(pid)
    db.set_meta("example_seeded", "1")      # don't recreate the example kid on the next start
    print(f"Deleted {pid} ({rec['input']['name']}) and {len(removed)} files: {', '.join(removed) or '-'}")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit("Usage: python backend/scripts/delete_player.py <player_id>")
    main(sys.argv[1].strip())
