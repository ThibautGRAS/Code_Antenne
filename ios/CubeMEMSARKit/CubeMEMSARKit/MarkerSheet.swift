import UIKit

/// Printable A4 PDF of the four ArUco markers (DICT_4X4_50 ID 0–3) at their real size,
/// drawn from the same cells as the ARKit reference images.
enum MarkerSheet {
    private static let pointsPerMm: CGFloat = 72 / 25.4
    private static let page = CGRect(x: 0, y: 0, width: 595.28, height: 841.89)
    private static let positions = [
        "en haut à gauche",
        "en haut à droite",
        "en bas à droite",
        "en bas à gauche"
    ]

    /// `markerSizeMm` is the side of the black square (border included), as set in the app.
    static func pdf(markerSizeMm: Double) -> Data {
        let size = CGFloat(markerSizeMm) * pointsPerMm
        let renderer = UIGraphicsPDFRenderer(bounds: page)

        // 2 × 2 markers per page when they fit, otherwise one per page.
        let perPage = size <= 255 ? 4 : 1

        return renderer.pdfData { context in
            var id = 0
            while id < 4 {
                context.beginPage()
                drawHeader(markerSizeMm: markerSizeMm)

                if perPage == 4 {
                    // Quiet zones (one cell) and labels must not overlap the header or each other.
                    let cell = size / 6
                    let gap: CGFloat = 40
                    let left = (page.width - 2 * size - gap) / 2
                    let top: CGFloat = 165
                    let rowStep = size + 2 * cell + 30
                    for index in 0..<4 {
                        let column = CGFloat(index == 0 || index == 3 ? 0 : 1)
                        let row = CGFloat(index < 2 ? 0 : 1)
                        let origin = CGPoint(x: left + column * (size + gap), y: top + row * rowStep)
                        drawMarker(id: index, at: origin, size: size)
                    }
                    id = 4
                } else {
                    drawMarker(id: id, at: CGPoint(x: (page.width - size) / 2, y: 170), size: size)
                    id += 1
                }

                drawScale()
            }
        }
    }

    private static func drawHeader(markerSizeMm: Double) {
        let title = "Cube MEMS AR — marqueurs ArUco (DICT_4X4_50)"
        title.draw(at: CGPoint(x: 40, y: 40), withAttributes: [
            .font: UIFont.boldSystemFont(ofSize: 16)
        ])

        let text = """
        Imprimer à 100 % (taille réelle, sans « ajuster à la page »). Le carré noir de chaque marqueur \
        doit mesurer \(String(format: "%.1f", markerSizeMm)) mm, comme le réglage « Taille ArUco » de l'app. \
        Coller les marqueurs à plat aux quatre coins de la face, vus de face : ID0 en haut à gauche, \
        ID1 en haut à droite, ID2 en bas à droite, ID3 en bas à gauche. Garder la marge blanche autour.
        """
        let paragraph = NSMutableParagraphStyle()
        paragraph.lineSpacing = 2
        text.draw(in: CGRect(x: 40, y: 66, width: page.width - 80, height: 80), withAttributes: [
            .font: UIFont.systemFont(ofSize: 10),
            .paragraphStyle: paragraph
        ])
    }

    private static func drawMarker(id: Int, at origin: CGPoint, size: CGFloat) {
        guard let cells = ArucoReferenceFactory.cells(id: id), let context = UIGraphicsGetCurrentContext() else { return }
        let cell = size / 6

        // White quiet zone (one cell) and a light cutting outline.
        let quiet = CGRect(x: origin.x - cell, y: origin.y - cell, width: size + 2 * cell, height: size + 2 * cell)
        context.setStrokeColor(UIColor(white: 0.75, alpha: 1).cgColor)
        context.setLineWidth(0.5)
        context.setLineDash(phase: 0, lengths: [3, 3])
        context.stroke(quiet)
        context.setLineDash(phase: 0, lengths: [])

        context.setFillColor(UIColor.black.cgColor)
        for row in 0..<6 {
            for column in 0..<6 where cells[row][column] == 0 {
                // Slight overlap avoids hairline gaps between black cells in some viewers.
                context.fill(CGRect(
                    x: origin.x + CGFloat(column) * cell,
                    y: origin.y + CGFloat(row) * cell,
                    width: cell + 0.3,
                    height: cell + 0.3
                ))
            }
        }

        let label = "ID\(id) — \(positions[id])"
        label.draw(at: CGPoint(x: origin.x - cell, y: origin.y + size + cell + 4), withAttributes: [
            .font: UIFont.boldSystemFont(ofSize: 11)
        ])
    }

    /// 100 mm ruler to check the print scale.
    private static func drawScale() {
        guard let context = UIGraphicsGetCurrentContext() else { return }
        let length = 100 * pointsPerMm
        let y = page.height - 42
        let x0: CGFloat = 40

        context.setStrokeColor(UIColor.black.cgColor)
        context.setLineWidth(1)
        context.move(to: CGPoint(x: x0, y: y))
        context.addLine(to: CGPoint(x: x0 + length, y: y))
        for mm in stride(from: 0, through: 100, by: 10) {
            let x = x0 + CGFloat(mm) * pointsPerMm
            let tick: CGFloat = mm % 50 == 0 ? 8 : 4
            context.move(to: CGPoint(x: x, y: y - tick))
            context.addLine(to: CGPoint(x: x, y: y))
        }
        context.strokePath()

        "Contrôle d'échelle : cette règle doit mesurer exactement 100 mm.".draw(
            at: CGPoint(x: x0, y: y + 5),
            withAttributes: [.font: UIFont.systemFont(ofSize: 9)]
        )
    }
}
