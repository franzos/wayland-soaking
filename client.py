from pywayland.client import Display


def main():
    # None: lookup WAYLAND_DISPLAY env; default to wayland-0
    display = Display(name_or_fd=None)
    is_connected = False
    try:
        display.connect()
        is_connected = True
        fd = display.get_fd()
        print("Connected to swayland on fd: %s!" % fd)
    except ValueError as err:
        print(err)

    if is_connected:
        display.disconnect()


main()
