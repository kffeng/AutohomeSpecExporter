#import <Cocoa/Cocoa.h>

@interface AppDelegate : NSObject <NSApplicationDelegate>
@property(nonatomic, strong) NSTimer *monitorTimer;
@property(nonatomic) BOOL backendSeen;
@property(nonatomic) NSInteger missedChecks;
@property(nonatomic) BOOL checking;
@end

@implementation AppDelegate

- (void)applicationDidFinishLaunching:(NSNotification *)notification {
    [self installMenu];
    [self runLauncher];
    self.monitorTimer = [NSTimer scheduledTimerWithTimeInterval:2.0
                                                        target:self
                                                      selector:@selector(checkBackend:)
                                                      userInfo:nil
                                                       repeats:YES];
}

- (BOOL)applicationShouldHandleReopen:(NSApplication *)sender hasVisibleWindows:(BOOL)flag {
    [self runLauncher];
    return NO;
}

- (void)openInterface:(id)sender {
    [self runLauncher];
}

- (NSString *)currentPort {
    NSString *dataDir = [@"~/Library/Application Support/AutohomeSpecExporter" stringByExpandingTildeInPath];
    NSString *portFile = [dataDir stringByAppendingPathComponent:@"runtime_port.txt"];
    NSString *value = [NSString stringWithContentsOfFile:portFile
                                                encoding:NSUTF8StringEncoding
                                                   error:nil];
    value = [value stringByTrimmingCharactersInSet:[NSCharacterSet whitespaceAndNewlineCharacterSet]];
    return value.length > 0 ? value : @"8765";
}

- (BOOL)backendHealthyAtPort:(NSString *)port {
    NSTask *task = [[NSTask alloc] init];
    task.executableURL = [NSURL fileURLWithPath:@"/usr/bin/curl"];
    task.arguments = @[
        @"-fsS",
        @"--max-time",
        @"1.5",
        [NSString stringWithFormat:@"http://127.0.0.1:%@/api/health", port]
    ];
    NSPipe *pipe = [NSPipe pipe];
    task.standardOutput = pipe;
    task.standardError = [NSFileHandle fileHandleWithNullDevice];
    NSError *error = nil;
    if (![task launchAndReturnError:&error]) {
        return NO;
    }
    NSData *data = [[pipe fileHandleForReading] readDataToEndOfFile];
    [task waitUntilExit];
    if (task.terminationStatus != 0) {
        return NO;
    }
    NSString *body = [[NSString alloc] initWithData:data encoding:NSUTF8StringEncoding];
    return [body containsString:@"汽车之家配置采集器"];
}

- (void)checkBackend:(NSTimer *)timer {
    if (self.checking) {
        return;
    }
    self.checking = YES;
    dispatch_async(dispatch_get_global_queue(QOS_CLASS_UTILITY, 0), ^{
        BOOL healthy = [self backendHealthyAtPort:[self currentPort]];
        dispatch_async(dispatch_get_main_queue(), ^{
            self.checking = NO;
            if (healthy) {
                self.backendSeen = YES;
                self.missedChecks = 0;
                return;
            }
            if (self.backendSeen) {
                self.missedChecks += 1;
                if (self.missedChecks >= 2) {
                    [self.monitorTimer invalidate];
                    [NSApp terminate:nil];
                }
            }
        });
    });
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
