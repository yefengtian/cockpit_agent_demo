import os
import subprocess
import sys
import time

from libs.config import get_setting

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

SERVICES = [
    ("audio_service",   "services.audio_service.app:app",   int(get_setting("services.audio_port", os.getenv("AUDIO_SERVICE_PORT", "8001")))),
    ("agent_service",   "services.agent_service.app:app",   int(get_setting("services.agent_port", os.getenv("AGENT_SERVICE_PORT", "8002")))),
    ("vehicle_service", "services.vehicle_service.app:app", int(get_setting("services.vehicle_port", os.getenv("VEHICLE_SERVICE_PORT", "8003")))),
    ("dms_service",     "services.dms_service.app:app",     int(get_setting("services.dms_port", os.getenv("DMS_SERVICE_PORT", "8004")))),
    ("nav_service",     "services.nav_service.app:app",     int(get_setting("services.nav_port", os.getenv("NAV_SERVICE_PORT", "8005")))),
]

def main():
    procs = []
    env = os.environ.copy()
    # 关键：让 ROOT 在 sys.path 上，这样 services/ libs/ 可导入
    env["PYTHONPATH"] = ROOT + (os.pathsep + env["PYTHONPATH"] if env.get("PYTHONPATH") else "")

    for name, app, port in SERVICES:
        cmd = [
            sys.executable, "-m", "uvicorn", app,
            "--host", "127.0.0.1",
            "--port", str(port),
        ]
        # 防御：过滤空参数
        cmd = [x for x in cmd if x]
        print(f"Starting {name} on :{port} ...")
        procs.append(subprocess.Popen(cmd, cwd=ROOT, env=env))

    print("\nAll services started. Press Ctrl+C to stop.\n")
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\nStopping...")
        for p in procs:
            p.terminate()
        for p in procs:
            try:
                p.wait(timeout=10)
            except Exception:
                pass

if __name__ == "__main__":
    main()
