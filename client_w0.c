#include <stdio.h>
#include <wayland-client.h>

int
main(int argc, char *argv[])
{   
    // connect to specific wayland server wayland-0
    struct wl_display *display = wl_display_connect("wayland-0");
    if (!display) {
        fprintf(stderr, "Failed to connect to Wayland display.\n");
        return 1;
    }
    fprintf(stderr, "Connected to wayland-0!\n");

    wl_display_disconnect(display);
    return 0;
}

