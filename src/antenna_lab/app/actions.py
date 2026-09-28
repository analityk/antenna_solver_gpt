from antenna_lab.antennas import build_model
from antenna_lab.core.geometry import check_geometry
from antenna_lab.core.runs import RunRecord
from antenna_lab.visualization.plots import geometry_plot


def start_record(config, output_root, stage):
    geometry = build_model(config)
    validation = check_geometry(geometry)
    record = RunRecord(output_root, stage, config, geometry, validation)
    try:
        geometry_plot(geometry, record.path / "plots" / "geometry.png")
    except Exception as exc:
        record.finish("failed", exc)
        raise
    return record


def export_geometry(config, output_root):
    record = start_record(config, output_root, "geometry")
    record.finish("completed")
    return record.path
