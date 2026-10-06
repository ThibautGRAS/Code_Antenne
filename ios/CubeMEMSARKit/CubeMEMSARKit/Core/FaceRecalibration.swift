import Foundation
import simd

// ArUco loop closure, without ARKit: once the face is locked, a re-observed marker gives a
// candidate face pose (marker world pose × inverse(marker local pose)); the face is moved
// a fraction of the way toward it. Used by ARScannerView and by the CI scan simulator.

enum FaceRecalibration {
    enum Outcome {
        /// `delta` maps the old face to the new one; apply it to every stored ray and point.
        case applied(newFace: simd_float4x4, delta: simd_float4x4, residualMm: Float, markerCount: Int)
        /// The candidate is too far from the current face: more likely a bad image-anchor pose.
        case rejected(translationJump: Float, rotationJump: Float)
    }

    static let maxTranslationJump: Float = 0.35
    static let maxRotationJump: Float = 20 * Float.pi / 180

    /// Smoothing toward the candidate per observation: 0.12 / 0.24 / 0.38 for 1 / 2 / ≥3 markers.
    static func blendFactor(markerCount: Int) -> Float {
        switch markerCount {
        case 1: return 0.12
        case 2: return 0.24
        default: return 0.38
        }
    }

    /// Returns nil when no observed marker has a stored local pose.
    static func soft(
        face oldFace: simd_float4x4,
        observed: [Int: simd_float4x4],
        markerLocal: [Int: simd_float4x4]
    ) -> Outcome? {
        var candidates: [simd_float4x4] = []

        for (id, markerWorld) in observed {
            guard let local = markerLocal[id] else { continue }
            candidates.append(markerWorld * simd_inverse(local))
        }

        guard let candidateFace = averageRigidTransforms(candidates, reference: oldFace) else { return nil }

        let oldQ = quaternion(from: oldFace)
        let candidateQ = quaternion(from: candidateFace)
        let qDot = min(1.0 as Float, max(0.0 as Float, abs(simd_dot(oldQ.vector, candidateQ.vector))))
        let rotationJump = 2.0 * acos(qDot)
        let translationJump = simd_distance(oldFace.translation, candidateFace.translation)

        // Do not move the whole reconstruction on one suspicious observation.
        if translationJump > maxTranslationJump || rotationJump > maxRotationJump {
            return .rejected(translationJump: translationJump, rotationJump: rotationJump)
        }

        let alpha = blendFactor(markerCount: candidates.count)
        let blendedTranslation =
            oldFace.translation +
            alpha * (candidateFace.translation - oldFace.translation)
        let blendedQ = simd_slerp(oldQ, candidateQ, alpha)
        let newFace = rigidTransform(rotation: blendedQ, translation: blendedTranslation)

        return .applied(
            newFace: newFace,
            delta: newFace * simd_inverse(oldFace),
            residualMm: markerResidualMm(face: candidateFace, observed: observed, markerLocal: markerLocal),
            markerCount: candidates.count
        )
    }

    /// RMS distance (mm) between observed marker centers and those predicted by `face`.
    static func markerResidualMm(
        face: simd_float4x4,
        observed: [Int: simd_float4x4],
        markerLocal: [Int: simd_float4x4]
    ) -> Float {
        var sum: Float = 0
        var count: Float = 0

        for (id, markerWorld) in observed {
            guard let local = markerLocal[id] else { continue }
            let predicted = (face * local).translation
            sum += simd_length_squared(predicted - markerWorld.translation)
            count += 1
        }

        guard count > 0 else { return 0 }
        return sqrt(sum / count) * 1000
    }

    static func averageRigidTransforms(
        _ transforms: [simd_float4x4],
        reference: simd_float4x4
    ) -> simd_float4x4? {
        guard !transforms.isEmpty else { return nil }

        var translation = SIMD3<Float>(repeating: 0)
        for transform in transforms {
            translation += transform.translation
        }
        translation /= Float(transforms.count)

        let referenceQ = quaternion(from: reference)
        var averageQ = referenceQ
        var accumulatedWeight: Float = 0

        for transform in transforms {
            var q = quaternion(from: transform)
            if simd_dot(referenceQ.vector, q.vector) < 0 {
                q = simd_quatf(vector: -q.vector)
            }

            let nextWeight = accumulatedWeight + 1
            averageQ = simd_slerp(averageQ, q, 1 / nextWeight)
            accumulatedWeight = nextWeight
        }

        return rigidTransform(rotation: averageQ, translation: translation)
    }

    static func quaternion(from transform: simd_float4x4) -> simd_quatf {
        simd_normalize(simd_quatf(transform.rotation))
    }

    static func rigidTransform(
        rotation: simd_quatf,
        translation: SIMD3<Float>
    ) -> simd_float4x4 {
        let x = rotation.act(SIMD3<Float>(1, 0, 0))
        let y = rotation.act(SIMD3<Float>(0, 1, 0))
        let z = rotation.act(SIMD3<Float>(0, 0, 1))

        var transform = matrix_identity_float4x4
        transform.columns.0 = SIMD4<Float>(x.x, x.y, x.z, 0)
        transform.columns.1 = SIMD4<Float>(y.x, y.y, y.z, 0)
        transform.columns.2 = SIMD4<Float>(z.x, z.y, z.z, 0)
        transform.columns.3 = SIMD4<Float>(translation.x, translation.y, translation.z, 1)
        return transform
    }
}
