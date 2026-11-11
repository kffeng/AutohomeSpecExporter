#include <libgen.h>
#include <limits.h>
#include <mach-o/dyld.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>

int main(void) {
    char executable[PATH_MAX];
    uint32_t size = sizeof(executable);
    if (_NSGetExecutablePath(executable, &size) != 0) {
        return 1;
    }

    char resolved[PATH_MAX];
    if (realpath(executable, resolved) == NULL) {
        return 1;
    }

    char script[PATH_MAX];
    int written = snprintf(script, sizeof(script), "%s/launcher.sh", dirname(resolved));
    if (written < 0 || written >= (int)sizeof(script)) {
        return 1;
    }

    execl("/bin/bash", "/bin/bash", script, (char *)NULL);
    perror("Unable to start launcher.sh");
    return 1;
}
