#!/usr/bin/env swift

import AVFoundation
import CoreGraphics
import Foundation
import ImageIO

let root = URL(fileURLWithPath: FileManager.default.currentDirectoryPath)
let assets = root.appendingPathComponent("docs/assets")
let output = assets.appendingPathComponent("labgraph-demo.mp4")
let images = ["demo-corpus.png", "demo-answer.png", "demo-trace.png"]
let width = 1440
let height = 900
let framesPerSecond: Int32 = 10
let secondsPerImage = 4

func loadImage(_ url: URL) throws -> CGImage {
    guard let source = CGImageSourceCreateWithURL(url as CFURL, nil),
          let image = CGImageSourceCreateImageAtIndex(source, 0, nil) else {
        throw NSError(domain: "LabGraphDemo", code: 1,
                      userInfo: [NSLocalizedDescriptionKey: "Could not load \(url.path)"])
    }
    return image
}

func pixelBuffer(for image: CGImage, pool: CVPixelBufferPool) throws -> CVPixelBuffer {
    var optionalBuffer: CVPixelBuffer?
    guard CVPixelBufferPoolCreatePixelBuffer(nil, pool, &optionalBuffer) == kCVReturnSuccess,
          let buffer = optionalBuffer else {
        throw NSError(domain: "LabGraphDemo", code: 2,
                      userInfo: [NSLocalizedDescriptionKey: "Could not allocate video frame"])
    }

    CVPixelBufferLockBaseAddress(buffer, [])
    defer { CVPixelBufferUnlockBaseAddress(buffer, []) }
    guard let context = CGContext(
        data: CVPixelBufferGetBaseAddress(buffer),
        width: width,
        height: height,
        bitsPerComponent: 8,
        bytesPerRow: CVPixelBufferGetBytesPerRow(buffer),
        space: CGColorSpaceCreateDeviceRGB(),
        bitmapInfo: CGImageAlphaInfo.noneSkipFirst.rawValue
    ) else {
        throw NSError(domain: "LabGraphDemo", code: 3,
                      userInfo: [NSLocalizedDescriptionKey: "Could not create frame context"])
    }

    context.setFillColor(CGColor(gray: 0.96, alpha: 1))
    context.fill(CGRect(x: 0, y: 0, width: width, height: height))
    let scale = min(CGFloat(width) / CGFloat(image.width),
                    CGFloat(height) / CGFloat(image.height))
    let drawWidth = CGFloat(image.width) * scale
    let drawHeight = CGFloat(image.height) * scale
    let rect = CGRect(
        x: (CGFloat(width) - drawWidth) / 2,
        y: (CGFloat(height) - drawHeight) / 2,
        width: drawWidth,
        height: drawHeight
    )
    context.interpolationQuality = .high
    context.draw(image, in: rect)
    return buffer
}

try? FileManager.default.removeItem(at: output)
let writer = try AVAssetWriter(outputURL: output, fileType: .mp4)
let input = AVAssetWriterInput(
    mediaType: .video,
    outputSettings: [
        AVVideoCodecKey: AVVideoCodecType.h264,
        AVVideoWidthKey: width,
        AVVideoHeightKey: height,
    ]
)
let adaptor = AVAssetWriterInputPixelBufferAdaptor(
    assetWriterInput: input,
    sourcePixelBufferAttributes: [
        kCVPixelBufferPixelFormatTypeKey as String: kCVPixelFormatType_32ARGB,
        kCVPixelBufferWidthKey as String: width,
        kCVPixelBufferHeightKey as String: height,
    ]
)
guard writer.canAdd(input) else { fatalError("Cannot add video input") }
writer.add(input)
guard writer.startWriting() else { throw writer.error! }
writer.startSession(atSourceTime: .zero)
guard let pool = adaptor.pixelBufferPool else { fatalError("No pixel buffer pool") }

var frameNumber: Int64 = 0
for filename in images {
    let image = try loadImage(assets.appendingPathComponent(filename))
    for _ in 0..<(secondsPerImage * Int(framesPerSecond)) {
        while !input.isReadyForMoreMediaData { Thread.sleep(forTimeInterval: 0.01) }
        let buffer = try pixelBuffer(for: image, pool: pool)
        let time = CMTime(value: frameNumber, timescale: framesPerSecond)
        guard adaptor.append(buffer, withPresentationTime: time) else {
            throw writer.error ?? NSError(domain: "LabGraphDemo", code: 4)
        }
        frameNumber += 1
    }
}

input.markAsFinished()
let completion = DispatchSemaphore(value: 0)
writer.finishWriting { completion.signal() }
completion.wait()
guard writer.status == .completed else { throw writer.error! }
print("Created \(output.path)")
