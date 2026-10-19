"""Make relative coverage XML paths repository-root relative for SonarQube."""

import sys
import xml.etree.ElementTree as ET
from pathlib import Path


def normalize_coverage_xml(report: Path, source_root: str) -> None:
    """Set Cobertura's source root and normalize platform separators."""
    tree = ET.parse(report)
    root = tree.getroot()
    repository_root = Path(__file__).resolve().parents[2]
    sources = root.find("sources")
    if sources is None:
        raise ValueError(f"No <sources> element in {report}")

    for source in list(sources):
        sources.remove(source)
    ET.SubElement(sources, "source").text = source_root

    for class_node in root.iter("class"):
        filename = class_node.get("filename")
        if filename is None:
            raise ValueError(f"Coverage class has no filename in {report}")
        normalized = filename.replace("\\", "/").lstrip("/")
        if normalized.startswith(f"{source_root}/"):
            normalized = normalized[len(source_root) + 1 :]
        if not (repository_root / source_root / normalized).is_file():
            raise ValueError(f"Coverage path does not exist: {source_root}/{normalized}")
        class_node.set("filename", normalized)

    tree.write(report, encoding="utf-8", xml_declaration=True)


if __name__ == "__main__":
    if len(sys.argv) != 3:
        raise SystemExit("usage: normalize_coverage_xml.py REPORT SOURCE_ROOT")
    normalize_coverage_xml(Path(sys.argv[1]), sys.argv[2])
