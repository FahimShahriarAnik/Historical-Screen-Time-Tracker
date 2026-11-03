// OCR helper for scripts/import_iphone.py — uses Apple's on-device Vision framework.
// Usage: swift scripts/ocr_helper.swift img1.png img2.png ...
// Prints one JSON object per image: {"file": ..., "lines": [{"text", "x", "y", "w", "h"}]}
// Coordinates are normalized 0–1 with origin at the TOP-left (Vision's native origin is bottom-left).
import Foundation
import Vision
import AppKit

for path in CommandLine.arguments.dropFirst() {
    guard let img = NSImage(contentsOfFile: path),
          let cg = img.cgImage(forProposedRect: nil, context: nil, hints: nil) else {
        FileHandle.standardError.write("cannot read \(path)\n".data(using: .utf8)!)
        continue
    }
    let req = VNRecognizeTextRequest()
    req.recognitionLevel = .accurate
    req.usesLanguageCorrection = false
    try? VNImageRequestHandler(cgImage: cg, options: [:]).perform([req])
    var lines: [[String: Any]] = []
    for obs in req.results ?? [] {
        guard let top = obs.topCandidates(1).first else { continue }
        let b = obs.boundingBox
        lines.append(["text": top.string,
                      "x": b.minX, "y": 1 - b.maxY, "w": b.width, "h": b.height])
    }
    let out: [String: Any] = ["file": path, "lines": lines]
    let data = try! JSONSerialization.data(withJSONObject: out)
    print(String(data: data, encoding: .utf8)!)
}
