# Soaking in Wayland (on guix)

WORK IN PROGRESS

I've recently gone all-in on Wayland, and while I really like the i3/Sway-way, there's much I've got on my mind to contribute, but not much knowledge on how it works under the hood.

Goals:

1. Displays all active application windows, across all workspaces.
2. Move application window from one workspace, to another

Current state: Way-what?

## First Steps

Sway is based on wlrools, so I decided to start there.

1. Learn and note the basics from Wayland Book (fantastic btw!)
2. Checkout libraries / bindings
3. Implement

[High-level design](https://wayland-book.com/introduction/high-level-design.html)

- mesa: abstraction of the graphic stack; OpenGL or Vulkan used in clients
- libinput: events from kernel related to input devices; access via Wayland compositor
- xkbcommon: translate keyboard codes to more generic symbols
- pixman: manipulate pixel buffer
- libwayland: protocol

### Protocol

- Primitives: `int`, `fixed`, `object`, `new_id` and types: `string`, `array`, `fd`, `enum`
- Messages
  - client: listen to events, send requests
  - server: listen for requests, send events
- Object IDs: track lifetime
- Transport: Unix socket 
  - `WAYLAND_SOCKET`
  - concat `WAYLAND_DISPLAY` with `XDG_RUNTIME_DIR`
  - concat `wayland-0` with `XDG_RUNTIME_DIR`

```bash
$ env
...
XDG_SESSION_TYPE=wayland
WAYLAND_DISPLAY=wayland-1
XDG_RUNTIME_DIR=/run/user/1000
```

Found the socket at `/run/user/1000/wayland-1`.

### libwayland

Most popular implementation of the protocol.

- wayland-util: structs, utility functions
- wayland-scanner: generate headers and code from protocol XML
- proxies and resources
  - client side: `wl_proxy`
  - server side: `wl_resources` (each owned by a single client)

Run XML file trough wayland-scanner -> interfaces, listeners.

#### Flow (server)

1. Lookup object ID and interface
2. Decode message
3. Invoke functions with arguments on object listeners

[Detailed example](https://wayland-book.com/libwayland/interfaces.html)

#### Display

Known as `wl_display`.

Run example client from the manual (`wl_display_connect`):

```bash
$ guix shell gcc-toolchain wayland
$ gcc -o client client.c -lwayland-client
$ ./client 
Connected to swayland!
```

This worked, because I already have a wayland server running.

Run example server (`wl_display_create`):

```bash
...
$ gcc -o server server.c -lwayland-server
$ ./server
Running Wayland display on wayland-0
```

> Using `wl_display_add_socket_auto` will allow libwayland to decide the name for the display automatically, which defaults to `wayland-0`, or `wayland-$n`, depending on whether any other Wayland compositors have sockets in `$XDG_RUNTIME_DIR`.

The server comes with it's own event loop `wl_event_loop`.

#### Globals & Registry

- `wl_display` initiates with object ID 1 already assigned
- use `wl_display::get_registry` to bind an object ID to `wl_registry`

Example:

```
C->S    00000001 000C0001 00000002            .... .... ....
        1.       2.       3.
```

1. object ID
2. - most significant 16bits, total length in bytes
   - least significant bits, request opcode
3. arguments

So, this calls request 1, on object ID 1 (`wl_display`), with new ID.

```xml
<interface name="wl_registry" version="1">
  <request name="bind">
    <arg name="name" type="uint" />
    <arg name="id" type="new_id" />
  </request>

  <event name="global">
    <arg name="name" type="uint" />
    <arg name="interface" type="string" />
    <arg name="version" type="uint" />
  </event>

  <event name="global_remove">
    <arg name="name" type="uint" />
  </event>
</interface>
```

##### Binding globals

- upon creation of registry obj, server emit `global` event
- to bind means, to take a known obj, and assign an ID

Run the example to print all global vars:

```bash
...
$ gcc -o globals globals.c -lwayland-client
$ WAYLAND_DISPLAY=wayland-0 WAYLAND_DEBUG=1 ./globals 
[1521924.028]  -> wl_display@1.get_registry(new id wl_registry@2)
[1521924.114]  -> wl_display@1.sync(new id wl_callback@3)
[1521924.267] wl_display@1.delete_id(3)
[1521924.314] wl_callback@3.done(0)
```

##### Registering globals

```bash
...
$ gcc -o server_reg_glob server_reg_glob.c -lwayland-server
```

I could not get this to compile, from the [example](https://wayland-book.com/registry/server-side.html). Probably my lack of experience with C. I will come back to this.

// TODO

#### Buffers & surfaces

- `wl_buffer`: container for pixels
- `wl_surface`: 
- `wl_compositor`: create surfaces and regions (on 0 or more outputs)
- `wl_shm`: shared memory (bind from registry)

Example allocation `wl_shm`:
- 1920x1080 window
- 4,147,200 pixel (double-buffering) format `WL_SHM_FORMAT_XRGB8888`
- Total: 16,588,800 bytes

#### XDG shell basics

Describes semantics for application windows.

- `xdg_surfaces`: "toplevel", "popup"

Defined in `/gnu/store/fcw4g0f3nf24a29qyn0zwmd33h2sh14d-wayland-protocols-1.32/share/wayland-protocols/stable/xdg-shell/xdg-shell.xml`

from zero to a window on-screen:

1. Bind to `wl_compositor` and use it to create a `wl_surface`.
2. Bind to `xdg_wm_base` and use it to create an` xdg_surface` with your `wl_surface`.
3. Create an `xdg_toplevel` from the `xdg_surface` with `xdg_surface.get_toplevel`.
4. Configure a listener for the `xdg_surface` and await the configure event.
5. Bind to the buffer allocation mechanism of your choosing (such as `wl_shm`) and allocate a shared buffer, then render your content to it.
6. Use `wl_surface.attach to attach` the `wl_buffer` to `the wl_surface`.
7. Use `xdg_surface.ack_configure`, passing it the serial from configure, acknowledging that you have prepared a suitable frame.
8. Send a `wl_surface.commit` request.

_Copied as is from [7.2. Application windows](https://wayland-book.com/xdg-shell-basics/xdg-toplevel.html)_.

The chapter comes with a complete example:

```bash
guix shell gcc-toolchain wayland
export XML_XDG_SHELL=/gnu/store/fcw4g0f3nf24a29qyn0zwmd33h2sh14d-wayland-protocols-1.32/share/wayland-protocols/stable/xdg-shell/xdg-shell.xml
wayland-scanner private-code < $XML_XDG_SHELL > xdg-shell-protocol.c
wayland-scanner client-header < $XML_XDG_SHELL > xdg-shell-client-protocol.h
gcc -o client_window client_window.x xdg-shell-protocol.c -lwayland-client -lrt
./client_window
```

You should see a rectangle with a square-pattern.

I've found that it will default to connect to my swayland at `wayland-1` given that the XDG env is set to that. Trying to connect to `wayland-0` (our example server) leads to a segmentation fault; I need to investigate this further.

```c
int
main(int argc, char *argv[])
{
    struct client_state state = { 0 };
    const char *name = "wayland-0";
    state.wl_display = wl_display_connect(name); 

    // rest
```

Segmentation fault, even though `wayland-1` works:

```bash
$ ./client_window 
Segmentation fault
```

#### Surfaces

- no state: initial
- pending state: negotiated between client and server
- applied state

States that are updated automically include `wl_buffer` (and transformations; rotate, subset), changed regions (damaged), opaque regions and scale.

Initial state is invalid:

1. assign a role (`xdg_toplevel`)
2. allocate, attach buffer
3. role-specific states
4. commit `wl_surface.commit` -> valid / mapped

##### Callbacks

Consider:
- a display with 60 Hz, can max. show 60 frames / s.
- application might be hidden, on another desktop

Best to listen to the compositor, when to provide new frames.
Compositor will send a `done` event, when it's ready to receive a new frame.


### wlroots Bindings

At this point I figured, why not checkout how this is implemented in other languages; naturally I select sway's compositor:

- ~~[wlroots-rs](https://github.com/swaywm/wlroots-rs)~~ [smithay](https://github.com/Smithay/smithay) rust
- [pywlroots](https://github.com/flacjacket/pywlroots) python
- [qwlroots](https://github.com/vioken/qwlroots) qt / qml
- [zig-wlroots](https://github.com/swaywm/zig-wlroots) zig
- [cl-wlroots](https://github.com/swaywm/cl-wlroots) lisp
- [hsroots](https://github.com/swaywm/hsroots) haskell

#### Python

##### Connecting

```bash
guix shell gcc-toolchain libxkbcommon python glib:out
python3 -m venv venv 
source venv/bin/activate
pip install pywlroots
export LD_LIBRARY_PATH=$LIBRARY_PATH
```

then run with:

```bash
$ python3 client.py
Connected to swayland on fd: 3!
```

Even though I know we're connected to `wayland-0` (`/run/user/1000/wayland-1`), I was wondering if I can trace that file descriptor.

```bash
$ ps -A | grep server
21318 pts/4    00:00:00 server
```

So we're looking for process 21318, with fd 3:

```bash
$ sudo ls -l /proc/*/fd/3 | grep 21318
lrwx------ 1 franz users 64 Jan  3 15:03 /proc/21318/fd/3 -> anon_inode:[eventpoll]
```

Not quite; Let's try to use `lsof` to find related, open files:

```bash
$ lsof grep | server
...
server    21318                      franz    6uW     REG               0,35         0       83 /run/user/1000/wayland-0.lock
server    21318                      franz    7u     unix 0x000000001683e502       0t0   177962 /run/user/1000/wayland-0 type=STREAM 
server    21318                      franz    8u     unix 0x000000001683e502       0t0   177962 /run/user/1000/wayland-0 type=STREAM
```

There we go: Our process 21318 is using the unix socket at `/run/user/1000/wayland-0` as expected.

##### Drawing a window

```bash
guix shell gcc-toolchain libxkbcommon python glib:out
python3 -m venv venv 
source venv/bin/activate
pip install pywlroots
export LD_LIBRARY_PATH=$LIBRARY_PATH
```

// TODO

Example doesn't work; started to work on an alterative but not there yet. Rel: https://github.com/flacjacket/pywayland/issues/46

---

# Misc

I want to setup an isolated environment, to try out wayland but I have problems establishing a session; Will get back to this later.

```bash
guix shell gcc-toolchain libxkbcommon python wayland coreutils glib:out grep \
  --emulate-fhs \
  --container \
  --network \
  --expose=/run/user/1000/wayland-0 \
  --expose=/run/user/1000/dbus-1 \
  --expose=/run \
  --preserve='^XDG_.*'
```
