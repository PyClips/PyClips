"""Mac and Android installer links. Run from the website folder:

python -m unittest tests.test_installers
"""

from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TMP = Path(tempfile.mkdtemp(prefix="pyclips-installers-"))
os.environ.setdefault("PYCLIPS_DATA_DIR", str(TMP))
os.environ.setdefault("PYCLIPS_ADMIN_PASSWORD", "test-admin-secret")
os.environ.setdefault("PYCLIPS_PUBLIC_URL", "http://127.0.0.1")

import sys

sys.path.insert(0, str(ROOT))

from fastapi.testclient import TestClient

from app import db
from app.main import app

MAC = "https://github.com/PyClips/PyClips/releases/download/mac-1.0.0/PyClips-1.0.0.dmg"
APK = "https://github.com/PyClips/PyClips/releases/download/android-0.3.0/PyClips-0.3.0.apk"


class InstallerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        db.get_conn()
        cls.client = TestClient(app)

    def setUp(self):
        db.delete_setting(db.MAC_INSTALLER_KEY)
        db.delete_setting(db.ANDROID_APK_KEY)
        self.client.post("/api/admin/login", json={"password": os.environ["PYCLIPS_ADMIN_PASSWORD"]})

    def test_admin_only(self):
        anon = TestClient(app)
        self.assertEqual(anon.post("/api/admin/installer/mac", json={"url": MAC}).status_code, 401)

    def test_set_redirect_and_clear(self):
        self.assertEqual(self.client.get("/download/mac", follow_redirects=False).status_code, 404)
        self.assertEqual(self.client.get("/api/download").json()["mac"], "")

        r = self.client.post("/api/admin/installer/mac", json={"url": MAC})
        self.assertEqual(r.status_code, 200, r.text)
        self.assertEqual(r.json()["filename"], "PyClips-1.0.0.dmg")
        r = self.client.post("/api/admin/installer/android", json={"url": APK})
        self.assertEqual(r.status_code, 200, r.text)

        pub = self.client.get("/api/download").json()
        self.assertEqual(pub["mac"], "/download/mac")
        self.assertEqual(pub["android"], "/download/android")
        r = self.client.get("/download/android", follow_redirects=False)
        self.assertEqual(r.status_code, 302)
        self.assertEqual(r.headers["location"], APK)

        self.client.post("/api/admin/installer/mac/clear", json={})
        self.assertEqual(self.client.get("/api/download").json()["mac"], "")
        self.assertEqual(self.client.get("/api/download").json()["android"], "/download/android")

    def test_rejects_wrong_file_or_host(self):
        self.assertEqual(self.client.post("/api/admin/installer/android", json={"url": MAC}).status_code, 400)
        bad = "https://example.com/releases/download/x/PyClips.dmg"
        self.assertEqual(self.client.post("/api/admin/installer/mac", json={"url": bad}).status_code, 400)
        self.assertEqual(self.client.get("/api/admin/installer/linux").status_code, 404)
        self.assertEqual(self.client.get("/download/linux", follow_redirects=False).status_code, 404)


if __name__ == "__main__":
    unittest.main()
