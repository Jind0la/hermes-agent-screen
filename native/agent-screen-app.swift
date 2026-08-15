// agent-screen-app.swift — Agent Screen: virtual display + native window + MJPEG.
//
// Copyright (c) 2022 Bastian Andelefski (DeskPad, https://github.com/Stengo/DeskPad)
// Copyright (c) 2021 Khaos Tian (CGVirtualDisplayPrivate.h / VirtualDisplayExp)
// Portions Copyright (c) 2026 Hermes Agent contributors
//
// This file is a fork of DeskPad (MIT). Substantial portions — virtual-display
// setup, CGDisplayStream → layer contents, click-to-warp, titlebar highlight,
// and window chrome — come from DeskPad. See ../NOTICE and ../LICENSE.deskpad.
//
// Hermes additions: loopback MJPEG server, drag-portal via Accessibility.
//
// Experimental: CGVirtualDisplay is private SPI and can break on any macOS update.
//
// Build: ./build-app.sh  (never ad-hoc codesign — Screen Recording TCC is
// bound to the signing identity).

import Cocoa
import CoreImage
import ImageIO
import Network
import UniformTypeIdentifiers
import ApplicationServices

// Unique from DeskPad's 0x1234/0x3456/0x0001 so both apps can run together.
private let kVendorID: UInt32 = 0x4845 // 'HE'
private let kProductID: UInt32 = 0x4153 // 'AS'
private let kSerialNum: UInt32 = 0x0001
private let kStreamMaxClients = 8
private let kJpegWidth = 1280

// MARK: - Runtime config (~/.hermes/agent-screen.json)
//
// The display name, JPEG cadence, native resolution and mode list are read at
// app start from ~/.hermes/agent-screen.json so they are configurable without
// recompiling. These Swift rules MUST match dashboard/config.py in this repo —
// that file is the canonical parser (pure functions + a `load(path)` that
// returns defaults on any error). Keep the two implementations in lockstep.
//
//   {
//     "displayName": "Agent Screen Display",  // trim, non-empty, <= 40 chars
//     "jpegEveryNthFrame": 20,                 // integer, clamped to 1...60
//     "nativeWidth": 3360,                     // both integers + on whitelist
//     "nativeHeight": 2100,
//     "modes": [[3360, 2100], ...]             // every pair on whitelist
//   }
//
// Resolution whitelist (width, height):
//   3360x2100, 3840x2160, 2560x1440, 1920x1080, 1600x900, 1280x720
// Missing file / invalid JSON / bad value -> defaults, never a crash.
struct RuntimeConfig {
    let displayName: String
    let jpegEveryNthFrame: Int
    let nativeWidth: Int
    let nativeHeight: Int
    let modes: [[Int]]

    static let defaultDisplayName = "Agent Screen Display"
    static let defaultJpegEveryNthFrame = 20
    static let displayNameMaxLen = 40
    static let jpegMin = 1
    static let jpegMax = 60
    static let defaultNativeWidth = 3360
    static let defaultNativeHeight = 2100
    static let defaultModes: [[Int]] = [
        [3360, 2100],
        [3840, 2160],
        [2560, 1440],
        [1920, 1080],
        [1600, 900],
        [1280, 720],
    ]

    /// The whitelist as "w:h" keys, so a pair lookup is O(1).
    private static var allowedResolutions: Set<String> {
        Set(defaultModes.map { "\($0[0]):\($0[1])" })
    }

    /// True when `n` is an NSNumber that represents a JSON integer (not a
    /// float, not a bool). JSONSerialization gives ints objCType "q", floats
    /// "d", bools CFBoolean (objCType "c") — so reject "d"/"f" and bools.
    /// This is the float-parity rule from the Eich-01 review: 3360.0 is NOT a
    /// valid integer here, matching Python's `isinstance(v, int)`.
    private static func isInt(_ n: NSNumber) -> Bool {
        if CFGetTypeID(n) == CFBooleanGetTypeID() { return false }
        let t = String(cString: n.objCType)
        return t != "d" && t != "f"
    }

    static func load() -> RuntimeConfig {
        var displayName = defaultDisplayName
        var jpegEveryNthFrame = defaultJpegEveryNthFrame
        var nativeWidth = defaultNativeWidth
        var nativeHeight = defaultNativeHeight
        var modes = defaultModes

        let path = FileManager.default.homeDirectoryForCurrentUser
            .appendingPathComponent(".hermes")
            .appendingPathComponent("agent-screen.json")
        guard let data = try? Data(contentsOf: path),
              let obj = (try? JSONSerialization.jsonObject(with: data)) as? [String: Any]
        else {
            return RuntimeConfig(displayName: displayName, jpegEveryNthFrame: jpegEveryNthFrame,
                                 nativeWidth: nativeWidth, nativeHeight: nativeHeight, modes: modes)
        }

        // displayName: String, trimmed non-empty and <= 40 chars, else default.
        if let raw = obj["displayName"] as? String {
            let trimmed = raw.trimmingCharacters(in: .whitespacesAndNewlines)
            if !trimmed.isEmpty, trimmed.count <= displayNameMaxLen {
                displayName = trimmed
            }
        }

        // jpegEveryNthFrame: Int clamped to 1...60, else default.
        if let raw = obj["jpegEveryNthFrame"] as? NSNumber, isInt(raw) {
            let value = raw.intValue
            jpegEveryNthFrame = min(max(value, jpegMin), jpegMax)
        }

        // nativeWidth/nativeHeight: only valid together — both JSON integers
        // AND the pair on the whitelist. Otherwise keep the default.
        if let w = obj["nativeWidth"] as? NSNumber, isInt(w),
           let h = obj["nativeHeight"] as? NSNumber, isInt(h) {
            let key = "\(w.intValue):\(h.intValue)"
            if allowedResolutions.contains(key) {
                nativeWidth = w.intValue
                nativeHeight = h.intValue
            }
        }

        // modes: array of [w, h] pairs, EVERY pair on the whitelist (both
        // entries JSON integers). Empty / non-array / any invalid pair ->
        // the default six modes.
        if let raw = obj["modes"] as? [Any], !raw.isEmpty {
            var parsed: [[Int]] = []
            var valid = true
            for item in raw {
                guard let pair = item as? [Any], pair.count == 2,
                      let w = pair[0] as? NSNumber, isInt(w),
                      let h = pair[1] as? NSNumber, isInt(h),
                      allowedResolutions.contains("\(w.intValue):\(h.intValue)")
                else {
                    valid = false
                    break
                }
                parsed.append([w.intValue, h.intValue])
            }
            if valid {
                modes = parsed
            }
        }

        return RuntimeConfig(displayName: displayName, jpegEveryNthFrame: jpegEveryNthFrame,
                             nativeWidth: nativeWidth, nativeHeight: nativeHeight, modes: modes)
    }
}

// MARK: - MJPEG server (loopback only — any local process can watch)

final class MJpegServer {
    private var listener: NWListener?
    private var clients: [NWConnection] = []
    private let queue = DispatchQueue(label: "mjpeg.server")
    private let port: NWEndpoint.Port

    init(port: NWEndpoint.Port = 8788) { self.port = port }

    func start() throws {
        let params = NWParameters.tcp
        params.allowLocalEndpointReuse = true
        params.requiredInterfaceType = .loopback
        let listener = try NWListener(using: params, on: port)
        listener.newConnectionHandler = { [weak self] conn in
            guard let self else { return }
            self.queue.async { self.handle(conn) }
        }
        listener.start(queue: queue)
        self.listener = listener
    }

    private func handle(_ conn: NWConnection) {
        conn.start(queue: queue)
        conn.receive(minimumIncompleteLength: 1, maximumLength: 8192) { [weak self] data, _, _, _ in
            guard let self, let data, let req = String(data: data, encoding: .utf8) else {
                conn.cancel()
                return
            }
            let line = req.split(separator: "\r\n", maxSplits: 1, omittingEmptySubsequences: true).first.map(String.init) ?? req
            if line.hasPrefix("GET /ping") {
                conn.send(content: Data("HTTP/1.1 200 OK\r\nContent-Length: 2\r\nConnection: close\r\n\r\nok".utf8),
                          completion: .contentProcessed { _ in conn.cancel() })
                return
            }
            let isStream = line.hasPrefix("GET /stream") || line.hasPrefix("GET / HTTP") || line == "GET /"
            guard isStream else {
                conn.send(content: Data("HTTP/1.1 404 Not Found\r\nContent-Length: 9\r\nConnection: close\r\n\r\nnot found".utf8),
                          completion: .contentProcessed { _ in conn.cancel() })
                return
            }
            self.queue.async {
                self.pruneClients()
                if self.clients.count >= kStreamMaxClients {
                    conn.send(content: Data("HTTP/1.1 503 Service Unavailable\r\nContent-Length: 11\r\nConnection: close\r\n\r\nbusy".utf8),
                              completion: .contentProcessed { _ in conn.cancel() })
                    return
                }
                let head = "HTTP/1.1 200 OK\r\nContent-Type: multipart/x-mixed-replace; boundary=frame\r\nCache-Control: no-cache\r\nConnection: keep-alive\r\n\r\n"
                conn.send(content: head.data(using: .utf8)!, completion: .contentProcessed { _ in
                    self.queue.async { self.clients.append(conn) }
                })
            }
        }
    }

    private func pruneClients() {
        clients.removeAll { conn in
            if case .failed = conn.state { return true }
            return conn.state == .cancelled
        }
    }

    func broadcast(_ jpeg: Data) {
        queue.async {
            self.pruneClients()
            let frame = Data("--frame\r\nContent-Type: image/jpeg\r\nContent-Length: \(jpeg.count)\r\n\r\n".utf8) + jpeg + Data("\r\n".utf8)
            for conn in self.clients {
                conn.send(content: frame, completion: .contentProcessed { _ in })
            }
        }
    }
}

// MARK: - AppDelegate: window + virtual display + stream

final class AppDelegate: NSObject, NSApplicationDelegate {
    private var window: NSWindow!
    private var contentView: NSView!
    private var display: CGVirtualDisplay!
    private var stream: CGDisplayStream?
    private var server = MJpegServer()
    private let ciContext = CIContext()
    private var frameCounter = 0
    private var axPrompted = false

    private var dragCandidateWindowID: CGWindowID = 0
    private var dragCandidatePID: pid_t = 0
    private var dragCandidateBounds: CGRect = .zero
    private var dragWasPressed = false
    private var dragSeenMovement = false
    private var dragWatchTimer: Timer?
    private var titlebarTimer: Timer?
    private var windowCloseObserver: NSObjectProtocol?

    /// Effective runtime config, read once at launch (see RuntimeConfig above).
    private let runtimeConfig = RuntimeConfig.load()

    func applicationDidFinishLaunching(_ notification: Notification) {
        let rect = NSRect(x: 0, y: 0, width: 960, height: 600)
        window = NSWindow(contentRect: rect,
                          styleMask: [.titled, .closable, .miniaturizable, .resizable],
                          backing: .buffered, defer: false)
        window.title = "Agent Screen"
        window.minSize = NSSize(width: 200, height: 125)
        // DeskPad chrome: transparent titlebar so backgroundColor tints it.
        window.titlebarAppearsTransparent = true
        window.isMovableByWindowBackground = true
        window.backgroundColor = .windowBackgroundColor
        contentView = NSView(frame: rect)
        contentView.wantsLayer = true
        contentView.layer?.backgroundColor = NSColor.black.cgColor
        window.contentView = contentView
        // Programmatic NSWindows default to isReleasedWhenClosed=true, so
        // AppKit frees the window on close while the delegate property still
        // points at it — the polling timers below then crash with
        // EXC_BAD_ACCESS (use-after-free on window.frame). Keep it alive.
        window.isReleasedWhenClosed = false
        window.center()
        // Show the window without stealing key focus from Hermes.
        window.orderFrontRegardless()

        contentView.addGestureRecognizer(NSClickGestureRecognizer(target: self, action: #selector(didClickOnScreen)))

        do {
            try server.start()
            NSLog("[agent-screen] MJPEG on http://127.0.0.1:8788/stream.mjpeg (loopback, unauthenticated)")
        } catch {
            NSLog("[agent-screen] server error: \(error)")
        }

        let descriptor = CGVirtualDisplayDescriptor()
        descriptor.setDispatchQueue(DispatchQueue.main)
        descriptor.name = runtimeConfig.displayName
        descriptor.maxPixelsWide = 5120
        descriptor.maxPixelsHigh = 2160
        descriptor.sizeInMillimeters = CGSize(width: 1600, height: 1000)
        descriptor.productID = kProductID
        descriptor.vendorID = kVendorID
        descriptor.serialNum = kSerialNum

        let display = CGVirtualDisplay(descriptor: descriptor)
        self.display = display

        let settings = CGVirtualDisplaySettings()
        settings.hiDPI = 1
        settings.modes = runtimeConfig.modes.map {
            CGVirtualDisplayMode(width: UInt($0[0]), height: UInt($0[1]), refreshRate: 60)
        }
        display.apply(settings)
        NSLog("[agent-screen] display created: ID \(display.displayID)")

        let stream = CGDisplayStream(
            dispatchQueueDisplay: display.displayID,
            outputWidth: runtimeConfig.nativeWidth,
            outputHeight: runtimeConfig.nativeHeight,
            pixelFormat: 1_111_970_369, // kCVPixelFormatType_32BGRA
            properties: [CGDisplayStream.showCursor: true] as CFDictionary,
            queue: .main,
            handler: { [weak self] _, _, frameSurface, _ in
                self?.handleFrame(surface: frameSurface)
            }
        )
        self.stream = stream
        stream?.start()
        NSLog("[agent-screen] CGDisplayStream running.")

        window.contentAspectRatio = NSSize(width: runtimeConfig.nativeWidth, height: runtimeConfig.nativeHeight)

        titlebarTimer = Timer.scheduledTimer(withTimeInterval: 0.25, repeats: true) { [weak self] _ in
            self?.updateTitlebarHighlight()
        }

        installWindowDragMonitor()

        // The drag/titlebar timers poll `window`; once the user closes the
        // window (or the app terminates) they must stop, or a late tick
        // touches a freed window (crash: tickDragWatch → window.frame).
        windowCloseObserver = NotificationCenter.default.addObserver(
            forName: NSWindow.willCloseNotification,
            object: window,
            queue: .main
        ) { [weak self] _ in
            self?.stopTimers()
        }
    }

    // MARK: - Drag portal (drop a foreign window onto us → teleport it)

    /// Polling, not an event monitor: title-bar drags are swallowed by
    /// WindowServer, so global monitors never see them. Each tick: left button
    /// down? is a foreign window moving? cursor over us? On release over us
    /// after movement → teleport via Accessibility.
    private func installWindowDragMonitor() {
        dragWatchTimer = Timer.scheduledTimer(withTimeInterval: 0.1, repeats: true) { [weak self] _ in
            self?.tickDragWatch()
        }
        NSLog("[agent-screen] drag portal on: drop a window onto this one to move it")
    }

    private func tickDragWatch() {
        let pressed = (NSEvent.pressedMouseButtons & 1) != 0
        let mouse = NSEvent.mouseLocation
        let overOurWindow = window.frame.contains(mouse)

        if pressed {
            if !dragWasPressed {
                if let info = windowInfo(at: mouse),
                   (info[kCGWindowOwnerName as String] as? String) != "Agent Screen",
                   (info[kCGWindowLayer as String] as? Int) == 0 {
                    dragCandidateWindowID = info[kCGWindowNumber as String] as? CGWindowID ?? 0
                    dragCandidatePID = info[kCGWindowOwnerPID as String] as? pid_t ?? 0
                    if let boundsDict = info[kCGWindowBounds as String] as? [String: CGFloat] {
                        dragCandidateBounds = CGRect(x: boundsDict["X"] ?? 0, y: boundsDict["Y"] ?? 0,
                                                     width: boundsDict["Width"] ?? 0, height: boundsDict["Height"] ?? 0)
                    }
                    dragSeenMovement = false
                } else {
                    dragCandidateWindowID = 0
                    dragCandidatePID = 0
                }
            } else if dragCandidateWindowID != 0, !dragSeenMovement {
                if let info = windowInfoByID(dragCandidateWindowID),
                   let boundsDict = info[kCGWindowBounds as String] as? [String: CGFloat] {
                    let now = CGRect(x: boundsDict["X"] ?? 0, y: boundsDict["Y"] ?? 0,
                                     width: boundsDict["Width"] ?? 0, height: boundsDict["Height"] ?? 0)
                    if abs(now.minX - dragCandidateBounds.minX) > 4 ||
                       abs(now.minY - dragCandidateBounds.minY) > 4 {
                        dragSeenMovement = true
                    }
                }
            }
        } else {
            if dragWasPressed, dragSeenMovement, overOurWindow,
               dragCandidateWindowID != 0, dragCandidatePID != 0 {
                moveWindowToAgentScreen(pid: dragCandidatePID, windowID: dragCandidateWindowID)
            }
            dragCandidateWindowID = 0
            dragCandidatePID = 0
            dragSeenMovement = false
        }
        dragWasPressed = pressed
    }

    /// Topmost normal (layer ≤ 0) window under a point. Dock/menu bar live on
    /// layer 20+ and must not win the hit-test.
    private func windowInfo(at point: CGPoint) -> [String: Any]? {
        guard let list = CGWindowListCopyWindowInfo([.optionOnScreenOnly, .excludeDesktopElements], kCGNullWindowID)
                as? [[String: Any]] else { return nil }
        let tol: CGFloat = 5
        var best: [String: Any]?
        var bestLayer = Int.min
        for info in list {
            guard let boundsDict = info[kCGWindowBounds as String] as? [String: CGFloat],
                  let alpha = info[kCGWindowAlpha as String] as? CGFloat, alpha > 0,
                  let layer = info[kCGWindowLayer as String] as? Int, layer <= 0 else { continue }
            let bounds = CGRect(x: boundsDict["X"] ?? 0, y: boundsDict["Y"] ?? 0,
                                width: boundsDict["Width"] ?? 0, height: boundsDict["Height"] ?? 0)
                .insetBy(dx: -tol, dy: -tol)
            if bounds.contains(point), layer > bestLayer {
                best = info
                bestLayer = layer
            }
        }
        return best
    }

    private func windowInfoByID(_ id: CGWindowID) -> [String: Any]? {
        guard let list = CGWindowListCopyWindowInfo([.optionOnScreenOnly, .excludeDesktopElements], kCGNullWindowID)
                as? [[String: Any]] else { return nil }
        return list.first { ($0[kCGWindowNumber as String] as? CGWindowID) == id }
    }

    private func ensureAccessibility() -> Bool {
        let opts = [kAXTrustedCheckOptionPrompt.takeUnretainedValue() as String: true] as CFDictionary
        let trusted = AXIsProcessTrustedWithOptions(opts)
        if !trusted, !axPrompted {
            axPrompted = true
            NSLog("[agent-screen] drag portal needs Accessibility permission (System Settings ▸ Privacy & Security ▸ Accessibility)")
        }
        return trusted
    }

    private func axValue(_ ref: CFTypeRef, _ type: AXValueType, _ dest: UnsafeMutableRawPointer) -> Bool {
        guard CFGetTypeID(ref) == AXValueGetTypeID() else { return false }
        return AXValueGetValue(unsafeBitCast(ref, to: AXValue.self), type, dest)
    }

    private func moveWindowToAgentScreen(pid: pid_t, windowID: CGWindowID) {
        guard ensureAccessibility() else { return }
        guard let screen = NSScreen.screens.first(where: { $0.localizedName.contains(runtimeConfig.displayName) }) else {
            NSLog("[agent-screen] drag portal: Agent Screen display not found")
            return
        }
        let appRef = AXUIElementCreateApplication(pid)
        var windowsRef: CFTypeRef?
        let err = AXUIElementCopyAttributeValue(appRef, kAXWindowsAttribute as CFString, &windowsRef)
        guard err == .success, let windows = windowsRef as? [AXUIElement] else {
            NSLog("[agent-screen] drag portal: AX window list failed (%@)", String(describing: err))
            return
        }
        var matchBounds = dragCandidateBounds
        if let info = windowInfoByID(windowID),
           let boundsDict = info[kCGWindowBounds as String] as? [String: CGFloat] {
            matchBounds = CGRect(x: boundsDict["X"] ?? 0, y: boundsDict["Y"] ?? 0,
                                 width: boundsDict["Width"] ?? 0, height: boundsDict["Height"] ?? 0)
        }
        let tolerance: CGFloat = 60
        var target: AXUIElement?
        for candidate in windows {
            var posRef: CFTypeRef?
            var sizeRef: CFTypeRef?
            guard AXUIElementCopyAttributeValue(candidate, kAXPositionAttribute as CFString, &posRef) == .success,
                  AXUIElementCopyAttributeValue(candidate, kAXSizeAttribute as CFString, &sizeRef) == .success,
                  let posValue = posRef,
                  let sizeValue = sizeRef else { continue }
            var pos = CGPoint.zero
            var size = CGSize.zero
            guard axValue(posValue, .cgPoint, &pos), axValue(sizeValue, .cgSize, &size) else { continue }
            let bounds = CGRect(origin: pos, size: size)
            if abs(bounds.minX - matchBounds.minX) < tolerance,
               abs(bounds.minY - matchBounds.minY) < tolerance,
               abs(bounds.width - matchBounds.width) < tolerance,
               abs(bounds.height - matchBounds.height) < tolerance {
                target = candidate
                break
            }
        }
        guard let axWindow = target else {
            NSLog("[agent-screen] drag portal: window %d not in AX list (PID %d)", windowID, pid)
            return
        }
        let center = NSPoint(x: screen.frame.midX, y: screen.frame.midY)
        var size = CGSize(width: 800, height: 500)
        var sizeRef: CFTypeRef?
        if AXUIElementCopyAttributeValue(axWindow, kAXSizeAttribute as CFString, &sizeRef) == .success,
           let sizeValue = sizeRef {
            _ = axValue(sizeValue, .cgSize, &size)
        }
        var newOrigin = CGPoint(x: center.x - size.width / 2, y: center.y - size.height / 2)
        if let posValue = AXValueCreate(.cgPoint, &newOrigin) {
            AXUIElementSetAttributeValue(axWindow, kAXPositionAttribute as CFString, posValue)
            NSLog("[agent-screen] drag portal: window %d → Agent Screen @ %@", windowID, NSStringFromPoint(newOrigin))
        }
    }

    private func updateTitlebarHighlight() {
        let mouse = NSEvent.mouseLocation
        let onAgentScreen = NSScreen.screens.contains {
            $0.localizedName.contains(runtimeConfig.displayName) && NSMouseInRect(mouse, $0.frame, false)
        }
        let target: NSColor = onAgentScreen
            ? NSColor(calibratedRed: 0.086, green: 0.639, blue: 0.290, alpha: 1.0) // #16A34A
            : NSColor.windowBackgroundColor
        if window.backgroundColor != target {
            window.backgroundColor = target
        }
    }

    private func handleFrame(surface: IOSurface?) {
        guard let surface else { return }
        contentView.layer?.contents = surface

        // Copy pixels on the stream queue (main) BEFORE the surface is recycled,
        // then JPEG-encode the owned CGImage off-thread. ~3 fps (every 20th frame
        // of a 60 Hz stream) by default — enough for the chip preview, cheap on
        // CPU. Cadence is configurable via ~/.hermes/agent-screen.json.
        frameCounter += 1
        guard frameCounter % runtimeConfig.jpegEveryNthFrame == 0 else { return }
        let ci = CIImage(ioSurface: surface)
        guard let cg = ciContext.createCGImage(ci, from: ci.extent) else { return }
        DispatchQueue.global(qos: .utility).async { [weak self] in
            self?.broadcastJPEG(cg)
        }
    }

    private func broadcastJPEG(_ cg: CGImage) {
        let targetW = kJpegWidth
        let scale = Double(targetW) / Double(cg.width)
        let targetH = max(1, Int(Double(cg.height) * scale))
        guard let ctx = CGContext(data: nil, width: targetW, height: targetH,
                                  bitsPerComponent: 8, bytesPerRow: 0,
                                  space: CGColorSpaceCreateDeviceRGB(),
                                  bitmapInfo: CGImageAlphaInfo.premultipliedLast.rawValue)
        else { return }
        ctx.draw(cg, in: CGRect(x: 0, y: 0, width: targetW, height: targetH))
        guard let scaled = ctx.makeImage(),
              let data = CFDataCreateMutable(nil, 0),
              let dest = CGImageDestinationCreateWithData(data, UTType.jpeg.identifier as CFString, 1, nil)
        else { return }
        CGImageDestinationAddImage(dest, scaled, [kCGImageDestinationLossyCompressionQuality: 0.55] as CFDictionary)
        if CGImageDestinationFinalize(dest) {
            server.broadcast(data as Data)
        }
    }

    @objc private func didClickOnScreen(_ gesture: NSGestureRecognizer) {
        let p = gesture.location(in: contentView)
        let w = contentView.bounds.width
        let h = contentView.bounds.height
        guard w > 0, h > 0, display != nil else { return }
        let dispW = CGFloat(runtimeConfig.nativeWidth)
        let dispH = CGFloat(runtimeConfig.nativeHeight)
        let x = p.x / w * dispW
        let y = (h - p.y) / h * dispH
        CGDisplayMoveCursorToPoint(display.displayID, CGPoint(x: x, y: y))
    }

    func applicationShouldTerminateAfterLastWindowClosed(_ sender: NSApplication) -> Bool {
        return true
    }

    func applicationWillTerminate(_ notification: Notification) {
        stopTimers()
    }

    private func stopTimers() {
        dragWatchTimer?.invalidate()
        dragWatchTimer = nil
        titlebarTimer?.invalidate()
        titlebarTimer = nil
    }
}

let app = NSApplication.shared
let delegate = AppDelegate()
app.delegate = delegate
app.setActivationPolicy(.regular)
app.run()
