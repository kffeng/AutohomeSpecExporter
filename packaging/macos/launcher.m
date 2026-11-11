#import <Cocoa/Cocoa.h>

@interface AppDelegate : NSObject <NSApplicationDelegate>
@end

@implementation AppDelegate

- (void)applicationDidFinishLaunching:(NSNotification *)notification {
    [self installMenu];
    [self runLauncher];
}

- (BOOL)applicationShouldHandleReopen:(NSApplication *)sender hasVisibleWindows:(BOOL)flag {
    [self runLauncher];
    return NO;
}

- (void)openInterface:(id)sender {
    [self runLauncher];
}

- (void)runLauncher {
    NSURL *executable = [[NSBundle mainBundle] executableURL];
    NSURL *script = [[executable URLByDeletingLastPathComponent] URLByAppendingPathComponent:@"launcher.sh"];
    NSTask *task = [[NSTask alloc] init];
    task.executableURL = [NSURL fileURLWithPath:@"/bin/bash"];
    task.arguments = @[script.path];
    task.standardOutput = [NSFileHandle fileHandleWithNullDevice];
    task.standardError = [NSFileHandle fileHandleWithNullDevice];
    NSError *error = nil;
    if (![task launchAndReturnError:&error]) {
        NSAlert *alert = [[NSAlert alloc] init];
        alert.messageText = @"汽车之家配置采集器启动失败";
        alert.informativeText = [NSString stringWithFormat:@"无法启动后台服务：%@", error.localizedDescription];
        alert.alertStyle = NSAlertStyleCritical;
        [alert runModal];
    }
}

- (void)installMenu {
    NSMenu *mainMenu = [[NSMenu alloc] init];
    NSMenuItem *applicationItem = [[NSMenuItem alloc] init];
    [mainMenu addItem:applicationItem];

    NSMenu *applicationMenu = [[NSMenu alloc] init];
    NSMenuItem *openItem = [[NSMenuItem alloc] initWithTitle:@"打开采集界面" action:@selector(openInterface:) keyEquivalent:@"o"];
    openItem.target = self;
    [applicationMenu addItem:openItem];
    [applicationMenu addItem:[NSMenuItem separatorItem]];
    [applicationMenu addItemWithTitle:@"退出汽车之家配置采集器" action:@selector(terminate:) keyEquivalent:@"q"];
    applicationItem.submenu = applicationMenu;
    NSApp.mainMenu = mainMenu;
}

@end

int main(void) {
    @autoreleasepool {
        NSApplication *application = [NSApplication sharedApplication];
        AppDelegate *delegate = [[AppDelegate alloc] init];
        application.delegate = delegate;
        [application setActivationPolicy:NSApplicationActivationPolicyRegular];
        [application run];
    }
    return 0;
}
