"""Empaqueta código y wheels Python 3.12; no incluye tests ni configuración privada."""
import hashlib
from pathlib import Path
import subprocess
import sys
import tempfile
from zipfile import ZipFile, ZipInfo, ZIP_DEFLATED
from backend.shared.config.settings import ROOT

ASSET_BUCKET = "flashdelivery-local-assets"


def build_package():
    output = ROOT / ".local" / "artifacts"
    output.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="flashdelivery-build-") as temp:
        stage = Path(temp)
        subprocess.run([sys.executable, "-m", "pip", "install", "--disable-pip-version-check",
                        "--no-compile", "--only-binary=:all:", "--platform", "manylinux2014_x86_64",
                        "--implementation", "cp", "--python-version", "3.12",
                        "-r", str(ROOT / "backend/requirements.txt"), "--target", str(stage)], check=True)
        for source in sorted((ROOT / "backend").rglob("*.py")):
            if "tests" in source.relative_to(ROOT / "backend").parts:
                continue
            target = stage / source.relative_to(ROOT)
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(source.read_bytes())
        archive = output / "backend.zip"
        with ZipFile(archive, "w", compression=ZIP_DEFLATED) as zipped:
            for source in sorted(stage.rglob("*")):
                if source.is_file() and "__pycache__" not in source.parts:
                    info = ZipInfo(source.relative_to(stage).as_posix(), date_time=(2020, 1, 1, 0, 0, 0))
                    info.compress_type = ZIP_DEFLATED
                    info.external_attr = 0o100644 << 16
                    zipped.writestr(info, source.read_bytes())
    digest = hashlib.sha256(archive.read_bytes()).hexdigest()
    return archive, f"backend/{digest}.zip"


def publish_package(settings):
    from botocore.exceptions import ClientError
    from backend.shared.infrastructure.clients import aws_client
    archive, key = build_package()
    client = aws_client("s3", settings)
    try:
        client.head_bucket(Bucket=ASSET_BUCKET)
    except ClientError as exc:
        if exc.response["Error"]["Code"] not in {"404", "NoSuchBucket", "NotFound"}:
            raise
        args = {"Bucket": ASSET_BUCKET}
        if settings.region != "us-east-1":
            args["CreateBucketConfiguration"] = {"LocationConstraint": settings.region}
        client.create_bucket(**args)
    client.put_object(Bucket=ASSET_BUCKET, Key=key, Body=archive.read_bytes())
    client.close()
    return key


if __name__ == "__main__":
    print(build_package())
