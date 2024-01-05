# Generously adapted from Sean Vig's example
# https://github.com/flacjacket/pywayland/blob/main/example/surface.py
#
# WIP https://github.com/flacjacket/pywayland/issues/46

import mmap

from pywayland.client import Display
from pywayland.protocol.xdg_shell import XdgWmBase
from pywayland.protocol.xdg_shell.xdg_surface import (
    XdgSurfaceProxy,
    XdgToplevel,
    XdgSurfaceResource,
)
from pywayland.protocol.xdg_shell.xdg_toplevel import XdgToplevelProxy
from pywayland.protocol.wayland import WlCompositor, WlShm
from pywayland.utils import AnonymousFile


WIDTH = 640
HEIGHT = 480
MARGIN = 10


class Window:
    def __init__(self):
        self.buffer = None
        self.compositor = None
        self.shell = None
        self.shm = None
        self.shm_data = None
        self.surface = None

        self.line_pos = MARGIN
        self.line_speed = +1


def shell_surface_ping_handler(shell_surface, serial):
    shell_surface.pong(serial)
    print("pinged/ponged")


def shm_format_handler(shm, format_):
    """
    argb, xargb must be supported minimum
    """
    if format_ == WlShm.format.argb8888.value:
        s = "ARGB8888"
    elif format_ == WlShm.format.xrgb8888.value:
        s = "XRGB8888"
    elif format_ == WlShm.format.rgb565.value:
        s = "RGB565"
    else:
        s = "other format"
    print(f"Possible shmem format: {s}")


def registry_global_handler(registry, oid, interface, version):
    window = registry.user_data
    if interface == "wl_compositor":
        print("got compositor")
        window.compositor = registry.bind(oid, WlCompositor, version)
    elif interface == "xdg_wm_base":
        print("got xdg_wm_base")
        window.shell = registry.bind(oid, XdgWmBase, version)
    elif interface == "wl_shm":
        print("got shm")
        window.shm = registry.bind(oid, WlShm, version)
        window.shm.dispatcher["format"] = shm_format_handler
    else:
        print("got %s" % interface)


def registry_global_remove(registry, oid):
    print("registry: remove %s" % oid)


# def registry_listener(registry):
#     registry.dispatcher["global"] = registry_global_handler
#     registry.dispatcher["global_remove"] = registry_global_remove


def create_buffer(window):
    stride = WIDTH * 4
    size = stride * HEIGHT

    with AnonymousFile(size) as fd:
        window.shm_data = mmap.mmap(
            fd, size, prot=mmap.PROT_READ | mmap.PROT_WRITE,
            flags=mmap.MAP_SHARED
        )
        pool = window.shm.create_pool(fd, size)
        buff = pool.create_buffer(
            0, WIDTH, HEIGHT, stride, WlShm.format.argb8888.value
        )
        pool.destroy()
    return buff


def create_window(window):
    window.buffer = create_buffer(window)
    window.surface.attach(window.buffer, 0, 0)
    window.surface.commit()


def redraw(callback, time, destroy_callback=True):
    window = callback.user_data
    if destroy_callback:
        callback._destroy()

    paint(window)
    window.surface.damage(0, 0, WIDTH, HEIGHT)

    callback = window.surface.frame()
    callback.dispatcher["done"] = redraw
    callback.user_data = window

    window.surface.attach(window.buffer, 0, 0)
    window.surface.commit()


def paint(window):
    mm = window.shm_data
    # clear
    mm.seek(0)
    mm.write(b"\xff" * 4 * WIDTH * HEIGHT)

    # draw progressing line
    mm.seek((window.line_pos * WIDTH + MARGIN) * 4)
    mm.write(b"\x00\x00\x00\xff" * (WIDTH - 2 * MARGIN))
    window.line_pos += window.line_speed

    # maybe reverse direction of progression
    if window.line_pos >= HEIGHT - MARGIN or window.line_pos <= MARGIN:
        window.line_speed = -window.line_speed


def main():
    window = Window()

    # None: lookup WAYLAND_DISPLAY env; default to wayland-0
    # (1) Connect to display
    display = Display(name_or_fd=None)

    try:
        display.connect()
        fd = display.get_fd()
        print("Connected to swayland on fd: %s!" % fd)
    except ValueError as err:
        print(err)
        return 1

    # (2) Get registry
    registry = display.get_registry()
    # (3) Listen for server events
    # registry_listener(registry)
    registry.dispatcher["global"] = registry_global_handler
    registry.dispatcher["global_remove"] = registry_global_remove
    registry.user_data = window

    display.dispatch(block=True)
    # (4) Block until all pending are done
    display.roundtrip()

    if window.compositor is None:
        raise RuntimeError("no compositor found")
    elif window.shell is None:
        raise RuntimeError("no shell found")
    elif window.shm is None:
        raise RuntimeError("no shm found")

    # (5) Create surface on compositor
    window.surface = window.compositor.create_surface()

    # (6) Create XDG surface from surface
    shell_surface: XdgSurfaceProxy = window.shell.get_xdg_surface(
        window.surface
    )

    # (7)

    # TODO: Everything below needs to be adapted #

    # (8)? Assign toplevel
    xdg_top_level: XdgToplevelProxy = shell_surface.get_toplevel()

    # shell_surface.ping()
    # window.surface.commit()

    # (9)? Set a title
    xdg_top_level.set_title("Example client")

    # xdg_top_level.configure()

    frame_callback = window.surface.frame()
    # redraw when notified by compositor
    # frame_callback.dispatcher["ping"] = shell_surface_ping_handler
    frame_callback.dispatcher["done"] = redraw
    frame_callback.user_data = window

    create_window(window)
    redraw(frame_callback, 0, destroy_callback=False)

    while display.dispatch(block=True) != -1:
        pass

    import time

    time.sleep(1)
    display.disconnect()


if __name__ == "__main__":
    main()
