// swift-tools-version:5.9
// Test harness for the ARKit-free reconstruction core.
// The same source folder (CubeMEMSARKit/Core) is compiled into the iOS app by Xcode.
// Run on a Mac: `cd ios/CubeMEMSARKit && swift test`
import PackageDescription

let package = Package(
    name: "CubeMEMSCore",
    platforms: [.macOS(.v13), .iOS(.v16)],
    products: [
        .library(name: "CubeMEMSCore", targets: ["CubeMEMSCore"])
    ],
    targets: [
        .target(
            name: "CubeMEMSCore",
            path: "CubeMEMSARKit/Core"
        ),
        .testTarget(
            name: "CubeMEMSCoreTests",
            dependencies: ["CubeMEMSCore"],
            path: "Tests/CubeMEMSCoreTests",
            resources: [.copy("Fixtures")]
        )
    ]
)
