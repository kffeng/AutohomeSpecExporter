import Cocoa

final class AppDelegate: NSObject, NSApplicationDelegate {
    private var launcherScript: URL {
        Bundle.main.executableURL!
            .deletingLastPathComponent()
            .appendingPathComponent("launcher.sh")
    }

    func applicationDidFinishLaunching(_ notification: Notification) {
        installMenu()
        runLauncher()
    }

    func applicationShouldHandleReopen(_ sender: NSApplication, hasVisibleWindows flag: Bool) -> Bool {
        runLauncher()
        return false
    }

    private func runLauncher() {
        let process = Process()
        process.executableURL = URL(fileURLWithPath: "/bin/bash")
        process.arguments = [launcherScript.path]
        process.standardOutput = FileHandle.nullDevice
        process.standardError = FileHandle.nullDevice
        do {
            try process.run()
        } catch {
            let alert = NSAlert()
            alert.messageText = "汽车之家配置采集器启动失败"
            alert.informativeText = "无法启动后台服务：\(error.localizedDescription)"
            alert.alertStyle = .critical
            alert.runModal()
        }
    }

    private func installMenu() {
        let mainMenu = NSMenu()
        let applicationItem = NSMenuItem()
        mainMenu.addItem(applicationItem)

        let applicationMenu = NSMenu()
        applicationMenu.addItem(
            withTitle: "打开采集界面",
            action: #selector(openInterface),
            keyEquivalent: "o"
        )
        applicationMenu.addItem(NSMenuItem.separator())
        applicationMenu.addItem(
            withTitle: "退出汽车之家配置采集器",
            action: #selector(NSApplication.terminate(_:)),
            keyEquivalent: "q"
        )
        applicationItem.submenu = applicationMenu
        NSApp.mainMenu = mainMenu
    }

    @objc private func openInterface() {
        runLauncher()
    }
}

let application = NSApplication.shared
let delegate = AppDelegate()
application.delegate = delegate
application.setActivationPolicy(.regular)
application.run()
