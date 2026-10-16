// Render one caption as a transparent PNG with CoreText (handles mixed Urdu/English bidi).
// Usage: caption <out.png> <canvasWidth> <text>
import AppKit

let args = CommandLine.arguments
let out = args[1], W = Int(args[2])!, text = args[3]
let pad = Int(Double(W) * 0.06)
let fontSize = CGFloat(W) * 0.058

let para = NSMutableParagraphStyle()
para.alignment = .center
para.baseWritingDirection = .natural
para.lineSpacing = fontSize * 0.15

let shadow = NSShadow()
shadow.shadowColor = NSColor(white: 0, alpha: 0.85)
shadow.shadowBlurRadius = fontSize * 0.2
shadow.shadowOffset = NSSize(width: 0, height: -fontSize * 0.06)

let attrs: [NSAttributedString.Key: Any] = [
    .font: NSFont.systemFont(ofSize: fontSize, weight: .heavy),
    .foregroundColor: NSColor.white,
    .strokeColor: NSColor.black,
    .strokeWidth: -2.0,
    .paragraphStyle: para,
    .shadow: shadow,
]
let str = NSAttributedString(string: text, attributes: attrs)
let inner = NSSize(width: W - 2 * pad, height: 10000)
let box = str.boundingRect(with: inner, options: [.usesLineFragmentOrigin, .usesFontLeading])
let H = Int(ceil(box.height)) + 2 * pad

let rep = NSBitmapImageRep(bitmapDataPlanes: nil, pixelsWide: W, pixelsHigh: H,
                           bitsPerSample: 8, samplesPerPixel: 4, hasAlpha: true, isPlanar: false,
                           colorSpaceName: .calibratedRGB, bytesPerRow: 0, bitsPerPixel: 0)!
NSGraphicsContext.saveGraphicsState()
NSGraphicsContext.current = NSGraphicsContext(bitmapImageRep: rep)
// dark rounded backing pill sized to the text, so captions read over busy collage
let tw = min(ceil(box.width), CGFloat(W - 2 * pad))
let px = fontSize * 0.55, py = fontSize * 0.3
let pill = NSRect(x: (CGFloat(W) - tw) / 2 - px, y: CGFloat(pad) - py,
                  width: tw + 2 * px, height: CGFloat(H - 2 * pad) + 2 * py)
NSColor(white: 0.05, alpha: 0.62).setFill()
NSBezierPath(roundedRect: pill, xRadius: fontSize * 0.45, yRadius: fontSize * 0.45).fill()
str.draw(with: NSRect(x: pad, y: pad, width: W - 2 * pad, height: H - 2 * pad),
         options: [.usesLineFragmentOrigin, .usesFontLeading])
NSGraphicsContext.restoreGraphicsState()
try! rep.representation(using: .png, properties: [:])!.write(to: URL(fileURLWithPath: out))
print("\(out) \(W)x\(H)")
