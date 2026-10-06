import Foundation
import simd

// Pure geometry of the capsule reconstruction: no ARKit, RealityKit or UIKit.
// Compiled into the app target and into the CubeMEMSCore Swift package
// (ios/CubeMEMSARKit/Package.swift) so it can be unit-tested on CI.

// MARK: - Observations and tracks

enum ObservationKind: Equatable {
    case white
    case orange
}

struct RayObservation {
    var origin: SIMD3<Float>
    var direction: SIMD3<Float>
}

struct DetectionObservation {
    var kind: ObservationKind
    var ray: RayObservation
    /// Intersection of the ray with the nominal microphone plane, in face-local XY.
    var localXY: SIMD2<Float>
}

enum TrackState: Equatable {
    case provisional
    case confirmed
    case rejected
}

struct MicroTrack {
    var kind: ObservationKind
    var rays: [RayObservation]
    var localXY: SIMD2<Float>
    var lastFrame: Int
    var seenThisFrame: Bool

    var worldPoint: SIMD3<Float>? = nil
    var depthError: Float = .greatestFiniteMagnitude
    var residual: Float = .greatestFiniteMagnitude
    var baseline: Float = 0
    var state: TrackState = .provisional
}

// MARK: - Face geometry

struct FaceGeometry {
    /// Face frame in world: X right, Y up, Z = face normal, origin at the face center (ArUco plane).
    var transform: simd_float4x4
    var width: Float
    var height: Float
    /// Offset of the microphone plane along the face normal, in meters.
    var planeOffset: Float

    var normal: SIMD3<Float> {
        simd_normalize(transform.zAxis)
    }

    var micPlaneOrigin: SIMD3<Float> {
        transform.transformPoint(SIMD3<Float>(0, 0, planeOffset))
    }

    /// Unsigned distance from a world point to the microphone plane.
    func planeDistance(_ point: SIMD3<Float>) -> Float {
        abs(simd_dot(point - micPlaneOrigin, normal))
    }

    /// Intersects a world ray with the microphone plane. Returns nil when the ray is parallel,
    /// points away, or hits outside the face rectangle enlarged by `margin`.
    func nominalIntersection(
        origin: SIMD3<Float>,
        direction: SIMD3<Float>,
        margin: Float = 0.10
    ) -> (world: SIMD3<Float>, local: SIMD3<Float>)? {
        let n = normal
        let denom = simd_dot(direction, n)
        guard abs(denom) > 1e-5 else { return nil }

        let distance = simd_dot(micPlaneOrigin - origin, n) / denom
        guard distance > 0 else { return nil }

        let world = origin + direction * distance
        let local = simd_inverse(transform).transformPoint(world)

        guard
            abs(local.x) <= width / 2 + margin,
            abs(local.y) <= height / 2 + margin
        else { return nil }

        return (world, local)
    }
}

// MARK: - Physical size filter

enum CapsuleSizeFilter {
    /// Expected blob diameter in pixels: focal_px × diameter_m / depth_m.
    static func expectedDiameterPixels(
        physicalDiameter: Float,
        depth: Float,
        focalPixels: Float
    ) -> Float {
        focalPixels * physicalDiameter / depth
    }

    static func passes(
        observedDiameterPixels: Float,
        physicalDiameter: Float,
        depth: Float,
        focalPixels: Float,
        tolerance: Float
    ) -> Bool {
        guard depth > 0.05 else { return false }

        let expected = expectedDiameterPixels(
            physicalDiameter: physicalDiameter,
            depth: depth,
            focalPixels: focalPixels
        )

        // Broad tolerance on purpose for the first tests:
        // perspective, partial masks and the net can alter the apparent blob size.
        let lower = expected * max(0.10, 1.0 - tolerance)
        let upper = expected * (1.0 + tolerance)
        return observedDiameterPixels >= lower && observedDiameterPixels <= upper
    }
}

// MARK: - Triangulation

enum Triangulation {
    /// Unweighted least-squares point closest to all rays:
    /// A = Σ(I − d dᵀ), b = Σ(I − d dᵀ) o, x = A⁻¹ b.
    /// The residual is the RMS perpendicular distance from the point to the rays.
    static func triangulate(
        _ rays: [RayObservation]
    ) -> (point: SIMD3<Float>, residual: Float)? {
        guard rays.count >= 2 else { return nil }

        var A = simd_float3x3(columns: (
            SIMD3<Float>(repeating: 0),
            SIMD3<Float>(repeating: 0),
            SIMD3<Float>(repeating: 0)
        ))
        var b = SIMD3<Float>(repeating: 0)
        let identity = matrix_identity_float3x3

        for ray in rays {
            let d = simd_normalize(ray.direction)
            let outer = simd_float3x3(columns: (d * d.x, d * d.y, d * d.z))
            let M = identity - outer
            A += M
            b += M * ray.origin
        }

        let determinant = simd_determinant(A)
        guard abs(determinant) > 1e-7 else { return nil }

        let point = simd_inverse(A) * b

        var sumSquared: Float = 0
        for ray in rays {
            let d = simd_normalize(ray.direction)
            let v = point - ray.origin
            let perpendicular = v - d * simd_dot(v, d)
            sumSquared += simd_length_squared(perpendicular)
        }

        return (point, sqrt(sumSquared / Float(rays.count)))
    }

    /// Largest distance between two ray origins.
    static func maximumBaseline(_ rays: [RayObservation]) -> Float {
        var result: Float = 0

        for i in 0..<rays.count {
            for j in (i + 1)..<rays.count {
                result = max(result, simd_distance(rays[i].origin, rays[j].origin))
            }
        }

        return result
    }
}

// MARK: - Track association and validation

struct ReconstructionParameters {
    /// Max face-plane XY distance to attach an observation to an existing track (m).
    var associationRadius: Float = 0.10
    var minRays = 4
    /// Min distance between two camera positions of a track (m).
    var minBaseline: Float = 0.20
    /// Max distance from the triangulated point to the microphone plane (m).
    var planeTolerance: Float = 0.08
    var maxRaysPerTrack = 30
    /// A track not updated for more frames than this can no longer receive observations.
    var associationMaxFrameGap = 40
    /// Non-confirmed tracks not updated for more frames than this are deleted.
    var pruneFrameGap = 50
}

struct TrackReconstructor {
    var parameters = ReconstructionParameters()
    private(set) var tracks: [MicroTrack] = []

    var confirmedCount: Int { tracks.filter { $0.state == .confirmed }.count }
    var provisionalCount: Int { tracks.filter { $0.state == .provisional }.count }
    var rejectedCount: Int { tracks.filter { $0.state == .rejected }.count }

    mutating func reset() {
        tracks.removeAll()
    }

    /// Associates one detection batch to the tracks, then re-evaluates every track.
    mutating func update(
        with observations: [DetectionObservation],
        frame: Int,
        face: FaceGeometry
    ) {
        for index in tracks.indices {
            tracks[index].seenThisFrame = false
        }

        for observation in observations {
            var bestIndex: Int?
            var bestDistance = Float.greatestFiniteMagnitude

            for index in tracks.indices {
                if tracks[index].seenThisFrame { continue }
                if frame - tracks[index].lastFrame > parameters.associationMaxFrameGap { continue }

                let distance = simd_distance(tracks[index].localXY, observation.localXY)
                let sameKind =
                    tracks[index].kind == observation.kind ||
                    observation.kind == .orange

                if sameKind && distance < bestDistance {
                    bestDistance = distance
                    bestIndex = index
                }
            }

            if let index = bestIndex, bestDistance < parameters.associationRadius {
                tracks[index].rays.append(observation.ray)
                if tracks[index].rays.count > parameters.maxRaysPerTrack {
                    tracks[index].rays.removeFirst()
                }
                tracks[index].localXY = observation.localXY
                tracks[index].lastFrame = frame
                tracks[index].seenThisFrame = true

                if observation.kind == .orange {
                    tracks[index].kind = .orange
                }
            } else {
                tracks.append(
                    MicroTrack(
                        kind: observation.kind,
                        rays: [observation.ray],
                        localXY: observation.localXY,
                        lastFrame: frame,
                        seenThisFrame: true
                    )
                )
            }
        }

        tracks.removeAll {
            $0.state != .confirmed &&
            frame - $0.lastFrame > parameters.pruneFrameGap
        }

        for index in tracks.indices {
            evaluateTrack(at: index, face: face)
        }
    }

    /// Applies a rigid world correction (ArUco loop closure) to every stored ray and point.
    mutating func applyWorldCorrection(_ delta: simd_float4x4) {
        let rotation = delta.rotation

        for index in tracks.indices {
            for rayIndex in tracks[index].rays.indices {
                tracks[index].rays[rayIndex].origin =
                    delta.transformPoint(tracks[index].rays[rayIndex].origin)
                tracks[index].rays[rayIndex].direction = simd_normalize(
                    rotation * tracks[index].rays[rayIndex].direction
                )
            }

            if let point = tracks[index].worldPoint {
                tracks[index].worldPoint = delta.transformPoint(point)
            }
        }
    }

    private mutating func evaluateTrack(at index: Int, face: FaceGeometry) {
        tracks[index].baseline = Triangulation.maximumBaseline(tracks[index].rays)

        if let result = Triangulation.triangulate(tracks[index].rays) {
            tracks[index].worldPoint = result.point
            tracks[index].residual = result.residual
            tracks[index].depthError = face.planeDistance(result.point)
        }

        let delta = parameters.planeTolerance
        let enoughGeometry =
            tracks[index].rays.count >= parameters.minRays &&
            tracks[index].baseline >= parameters.minBaseline

        let residualLimit = max(0.10, delta * 1.5)

        if enoughGeometry &&
            tracks[index].depthError <= delta &&
            tracks[index].residual <= residualLimit
        {
            tracks[index].state = .confirmed
        } else if enoughGeometry && tracks[index].depthError > delta * 1.5 {
            tracks[index].state = .rejected
        } else {
            tracks[index].state = .provisional
        }
    }
}

// MARK: - simd helpers

extension simd_float4x4 {
    var translation: SIMD3<Float> {
        SIMD3<Float>(columns.3.x, columns.3.y, columns.3.z)
    }

    var zAxis: SIMD3<Float> {
        SIMD3<Float>(columns.2.x, columns.2.y, columns.2.z)
    }

    var rotation: simd_float3x3 {
        simd_float3x3(columns: (
            SIMD3<Float>(columns.0.x, columns.0.y, columns.0.z),
            SIMD3<Float>(columns.1.x, columns.1.y, columns.1.z),
            SIMD3<Float>(columns.2.x, columns.2.y, columns.2.z)
        ))
    }

    func transformPoint(_ point: SIMD3<Float>) -> SIMD3<Float> {
        let result = self * SIMD4<Float>(point.x, point.y, point.z, 1)
        return SIMD3<Float>(result.x, result.y, result.z)
    }
}
