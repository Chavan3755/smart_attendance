import subprocess

def before_install():
    packages = [
        "cmake",
        "build-essential",
        "libopencv-dev",
        "python3-dev"
    ]

    cmd = ["apt-get", "install", "-y"] + packages

    try:
        subprocess.check_call(cmd)
    except Exception as e:
        raise RuntimeError(f"System dependency install failed: {e}")
