import sys
import os
import traceback

def resolve_path(path):
    if getattr(sys, 'frozen', False):
        basedir = sys._MEIPASS
    else:
        basedir = os.path.dirname(__file__)
    return os.path.join(basedir, path)

def write_log(msg):
    """Write to medtify_log.txt next to the exe"""
    if getattr(sys, 'frozen', False):
        log_dir = os.path.dirname(sys.executable)
    else:
        log_dir = os.path.dirname(__file__)
    log_path = os.path.join(log_dir, "medtify_log.txt")
    with open(log_path, "a", encoding="utf-8") as f:
        f.write(msg + "\n")

if __name__ == "__main__":
    try:
        write_log(f"=== Medtify V15 (Evolution API) {sys.version} ===")
        write_log(f"frozen: {getattr(sys, 'frozen', False)}")
        
        if getattr(sys, 'frozen', False):
            write_log(f"MEIPASS: {sys._MEIPASS}")
            write_log(f"executable: {sys.executable}")
            files = os.listdir(sys._MEIPASS)
            write_log(f"Files in MEIPASS: {len(files)}")
            for f in sorted(files)[:30]:
                write_log(f"  {f}")
            app_path = resolve_path("medtify_app_v15.py")
            write_log(f"App path: {app_path}")
            write_log(f"App exists: {os.path.exists(app_path)}")
            st_path = os.path.join(sys._MEIPASS, ".streamlit", "config.toml")
            write_log(f"Config exists: {os.path.exists(st_path)}")
        
        import streamlit.web.cli as stcli
        
        app_path = resolve_path("medtify_app_v15.py")
        write_log(f"Running streamlit with: {app_path}")
        
        sys.argv = [
            "streamlit",
            "run",
            app_path,
            "--global.developmentMode=false",
        ]
        
        sys.exit(stcli.main())
        
    except Exception as e:
        write_log(f"ERROR: {type(e).__name__}: {e}")
        write_log(traceback.format_exc())
        input("Press Enter to exit...")
