// Wi-Fi multi-AP kamermeting (macOS Sequoia en nieuwer)
// Frameworks: CoreWLAN, CoreLocation, AppKit. Geen externe dependencies.
import Foundation
import AppKit
import CoreWLAN
import CoreLocation

final class WifiScanApp: NSObject, NSApplicationDelegate, CLLocationManagerDelegate {
    private let manager = CLLocationManager()
    private var started = false

    func applicationDidFinishLaunching(_ notification: Notification) {
        manager.delegate = self
        if manager.authorizationStatus == .notDetermined {
            manager.requestWhenInUseAuthorization()
            // Ook bij een geweigerde/weggeklikte prompt willen we een diagnostisch JSON-bestand.
            DispatchQueue.main.asyncAfter(deadline: .now() + 45) { [weak self] in self?.startOnce() }
        } else {
            startOnce()
        }
    }

    func locationManagerDidChangeAuthorization(_ manager: CLLocationManager) {
        if manager.authorizationStatus != .notDetermined { startOnce() }
    }

    private func startOnce() {
        guard !started else { return }
        started = true
        if manager.authorizationStatus == .authorizedAlways {
            manager.startUpdatingLocation()
        }
        let permission = manager.authorizationStatus
        DispatchQueue.global(qos: .userInitiated).async {
            self.scan(permission: permission)
            DispatchQueue.main.async {
                self.manager.stopUpdatingLocation()
                NSApp.terminate(nil)
            }
        }
    }

    private func scan(permission: CLAuthorizationStatus) {
        let args = CommandLine.arguments
        func option(_ key: String) -> String? {
            guard let idx = args.firstIndex(of: key), idx + 1 < args.count else { return nil }
            return args[idx + 1]
        }
        guard let file = option("--output"), let ssid = option("--ssid"), !ssid.isEmpty else {
            NSLog("WifiScan: --output en --ssid ontbreken")
            return
        }
        let ifaceName = option("--interface") ?? "en0"
        let count = min(12, max(1, Int(option("--count") ?? "4") ?? 4))
        let delay = min(30.0, max(0, Double(option("--interval") ?? "2") ?? 2))
        var result: [String: Any] = [
            "scan_schema": 1,
            "ssid": ssid,
            "wifi_interface": ifaceName,
            "gevraagde_scans": count,
            "location_authorisatie": statusName(permission),
            "scans": [[String: Any]](),
            "waarschuwingen": [String]()
        ]
        var warnings: [String] = []
        var scans: [[String: Any]] = []
        if permission != .authorizedAlways {
            warnings.append("Locatietoegang voor WifiKamermeting ontbreekt. SSID/BSSID kunnen verborgen zijn. Open System Settings > Privacy & Security > Location Services.")
        }
        let client = CWWiFiClient.shared()
        guard let iface = client.interface(withName: ifaceName) else {
            warnings.append("CoreWLAN kan interface \(ifaceName) niet openen.")
            result["waarschuwingen"] = warnings
            writeJSON(result, to: file)
            return
        }
        for index in 0..<count {
            if index > 0 && delay > 0 { Thread.sleep(forTimeInterval: delay) }
            var entry: [String: Any] = [
                "nummer": index + 1,
                "tijdstip_utc": stamp(),
                "aps": [[String: Any]]()
            ]
            let currentBSSID = normalizedBSSID(iface.bssid())
            entry["verbonden_bssid"] = currentBSSID as Any? ?? NSNull()
            entry["verbonden_ssid"] = iface.ssid() as Any? ?? NSNull()
            let connectedRSSI = iface.rssiValue()
            entry["verbonden_rssi_dbm"] = validRSSI(connectedRSSI) ? connectedRSSI as Any : NSNull()
            do {
                // Gerichte scan: alleen het gevraagde SSID. Iedere CWNetwork is een radio/BSSID.
                let networks = try iface.scanForNetworks(withSSID: Data(ssid.utf8))
                var aps: [[String: Any]] = []
                var redacted = 0
                for network in networks {
                    // Bij toegangsblokkade kan de SSID nil zijn ondanks gerichte scan.
                    if let returnedSSID = network.ssid, returnedSSID != ssid { continue }
                    guard let bssid = normalizedBSSID(network.bssid) else {
                        redacted += 1
                        continue  // Nooit niet-geïdentificeerde radios samenvoegen.
                    }
                    let rssi = network.rssiValue
                    guard validRSSI(rssi) else { continue }
                    let channel = network.wlanChannel?.channelNumber
                    var ap: [String: Any] = ["bssid": bssid, "rssi_dbm": rssi]
                    ap["kanaal"] = channel as Any? ?? NSNull()
                    let noise = network.noiseMeasurement
                    ap["ruis_dbm"] = validRSSI(noise) ? noise as Any : NSNull()
                    aps.append(ap)
                }
                aps.sort {
                    let a = $0["rssi_dbm"] as? Int ?? -999
                    let b = $1["rssi_dbm"] as? Int ?? -999
                    return a == b ? ($0["bssid"] as? String ?? "") < ($1["bssid"] as? String ?? "") : a > b
                }
                entry["aps"] = aps
                entry["verborgen_bssid_aantal"] = redacted
                if redacted > 0 {
                    warnings.append("Scan \(index + 1): \(redacted) AP(s) gevonden maar BSSID verborgen door macOS; niet toegevoegd als geïdentificeerde AP.")
                }
            } catch {
                entry["fout"] = error.localizedDescription
                warnings.append("Scan \(index + 1) mislukt: \(error.localizedDescription)")
            }
            scans.append(entry)
        }
        result["scans"] = scans
        result["waarschuwingen"] = Array(Set(warnings)).sorted()
        writeJSON(result, to: file)
    }

    private func writeJSON(_ json: [String: Any], to path: String) {
        do {
            let data = try JSONSerialization.data(withJSONObject: json, options: [.prettyPrinted, .sortedKeys])
            try data.write(to: URL(fileURLWithPath: path), options: .atomic)
        } catch {
            NSLog("WifiScan kan geen JSON schrijven: \(error)")
        }
    }
}

private func normalizedBSSID(_ original: String?) -> String? {
    guard let value = original?.lowercased() else { return nil }
    let parts = value.split(separator: ":")
    guard parts.count == 6 && parts.allSatisfy({ part in
        part.count == 2 && part.unicodeScalars.allSatisfy({ CharacterSet(charactersIn: "0123456789abcdef").contains($0) })
    }) else { return nil }
    return value
}
private func validRSSI(_ n: Int) -> Bool { n >= -110 && n <= -1 }
private func stamp() -> String {
    let formatter = ISO8601DateFormatter()
    formatter.formatOptions = [.withInternetDateTime]
    return formatter.string(from: Date())
}
private func statusName(_ status: CLAuthorizationStatus) -> String {
    switch status {
    case .authorizedAlways: return "granted"
    case .denied: return "denied"
    case .restricted: return "restricted"
    case .notDetermined: return "not_determined"
    @unknown default: return "unknown"
    }
}

@main
struct EntryPoint {
    static func main() {
        let app = NSApplication.shared
        let delegate = WifiScanApp()
        app.delegate = delegate
        app.run()
    }
}
