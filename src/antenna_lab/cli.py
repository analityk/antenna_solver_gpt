"""Windows-friendly entry point; native solves run in a separate process."""

import argparse
import json
import os
from pathlib import Path
import subprocess
import sys

from antenna_lab.core.config import ConfigurationError, ROOT, load_config, modified_config


def parser():
    root = argparse.ArgumentParser(prog="python -m antenna_lab", description="Parametryczne anteny i openEMS")
    commands = root.add_subparsers(dest="command", required=True)
    descriptions = {"preview": "Edytor i podgląd geometrii (bez obliczeń EM)",
                    "check": "Kontrola wymiarów, połączeń i siatki", "geometry": "Zapis geometrii i rysunku",
                    "prepare": "Zapis pełnego wejścia openEMS XML (bez uruchamiania FDTD)",
                    "run": "Uruchomienie openEMS i zapis roboczych wyników"}
    for name, description in descriptions.items():
        command = commands.add_parser(name, help=description)
        command.add_argument("--config", type=Path, default=ROOT / "parameters" / "quados8_1420mhz.json")
        command.add_argument("--output", type=Path, default=ROOT / "outcomes" / "runs")
        command.add_argument("--set-mm", action="append", default=[], metavar="C=75", help="Zmień wymiar w mm; opcję można powtórzyć")
        frequencies = command.add_mutually_exclusive_group()
        frequencies.add_argument("--frequency-mhz", type=float, help="Zmień częstotliwość, zachowując wymiary")
        frequencies.add_argument("--scale-to-mhz", type=float, help="Jawnie przeskaluj wszystkie wymiary i częstotliwość")
        reflector = command.add_mutually_exclusive_group()
        reflector.add_argument("--no-reflector", dest="reflector", action="store_false")
        reflector.add_argument("--reflector", dest="reflector", action="store_true")
        command.set_defaults(reflector=None)
    report = commands.add_parser("report", help="Lokalny HTML z zapisanych wyników; bez FDTD")
    report.add_argument("run_dir", nargs="?", type=Path, help="Katalog wyników symulacji")
    report.add_argument("--latest", action="store_true", help="Najnowsza ukończona symulacja")
    report.add_argument("--runs-dir", type=Path, default=ROOT / "outcomes" / "runs")
    report.add_argument("--output", type=Path, help="Nowy plik .html; domyślnie outcomes/reports")
    report.add_argument("--open", action="store_true", help="Otwórz HTML w domyślnej przeglądarce")
    report.add_argument("--start-mhz", type=float, help="Opcjonalny początek widma z surowych sond portu")
    report.add_argument("--stop-mhz", type=float, help="Opcjonalny koniec widma z surowych sond portu")
    report.add_argument("--step-mhz", type=float, help="Krok widma; wymaga obu granic i zapisanych sond")
    worker = commands.add_parser("_worker", help=argparse.SUPPRESS)
    worker.add_argument("--run-dir", type=Path, required=True)
    worker.add_argument("--mode", choices=["prepare", "run"], required=True)
    return root


def _worker(args):
    from antenna_lab.antennas import build_model
    from antenna_lab.core.runs import RunRecord
    from antenna_lab.solvers.openems import prepare, solve
    record = RunRecord.open(args.run_dir)
    if record.manifest["status"] != "running":
        raise ConfigurationError("Ten przebieg jest już zakończony. Uruchom prepare lub run, aby utworzyć nowy katalog.")
    try:
        config = load_config(record.path / "parameters.resolved.json")
        print("Budowanie wejścia openEMS...", flush=True)
        prepared = prepare(build_model(config), config, record)
        print("Zapisano openems/model.xml.", flush=True)
        if args.mode == "run":
            print("Uruchamianie FDTD. Ctrl+C w terminalu przerywa obliczenie.", flush=True)
            solve(prepared, config, record)
            record.save()
        return 0
    except Exception as exc:
        record.manifest["error"] = f"{type(exc).__name__}: {exc}"
        record.save()
        print(record.manifest["error"], file=sys.stderr, flush=True)
        return 1


def _stop_worker(process):
    if process is not None and process.poll() is None:
        process.terminate()
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait()


def _read_worker_log(process, log):
    try:
        for line in process.stdout:
            log.write(line)
            log.flush()
            print(line, end="", flush=True)
            if "Can't open file:" in line:
                # Upstream only prints this failure and keeps solving. Stop our
                # worker immediately: a missing probe cannot be recovered later.
                _stop_worker(process)
                raise RuntimeError("Przerwano openEMS po błędzie otwarcia pliku: " + line.strip())
    finally:
        process.stdout.close()


def _native_job(config, output, mode):
    from antenna_lab.app.actions import start_record
    from antenna_lab.core.runs import RunRecord
    record = start_record(config, output, "openems_input" if mode == "prepare" else "simulation")
    print(f"Wyniki: {record.path}", flush=True)
    command = [sys.executable, "-m", "antenna_lab", "_worker", "--run-dir", str(record.path), "--mode", mode]
    environment = dict(os.environ, PYTHONUNBUFFERED="1", PYTHONIOENCODING="utf-8", MPLBACKEND="Agg")
    process = None
    try:
        with (record.path / "solver.log").open("w", encoding="utf-8") as log:
            process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                       text=True, encoding="utf-8", errors="replace", env=environment)
            _read_worker_log(process, log)
            exit_code = process.wait()
        record = RunRecord.open(record.path)
        if exit_code != 0:
            raise RuntimeError(record.manifest["error"] or f"Proces openEMS zakończył się kodem {exit_code}; zobacz solver.log.")
        if mode == "run":
            if config["solver"].get("power_diagnostics"):
                from antenna_lab.solvers.power import pack_diagnostics
                print(f"Paczka diagnostyczna: {pack_diagnostics(record.path)}", flush=True)
            _write_run_report(record)
        record.finish("prepared" if mode == "prepare" else "completed")
        print("Wejście openEMS przygotowane." if mode == "prepare" else "Obliczenie zakończone. Wynik roboczy: wymagane sprawdzenie zbieżności.")
        print(f"Katalog: {record.path}")
        return 0
    except KeyboardInterrupt:
        _stop_worker(process)
        record = RunRecord.open(record.path)
        record.finish("cancelled", "Przerwano przez użytkownika.")
        print(f"Przerwano. Zachowane pliki: {record.path}")
        return 130
    except Exception as exc:
        _stop_worker(process)
        record = RunRecord.open(record.path)
        record.finish("failed", exc)
        raise


def _write_run_report(record):
    """A presentation failure must not discard a successful expensive solve."""
    try:
        from antenna_lab.visualization.report import generate_report
        path = generate_report(record.path, automatic=True)
        print(f"Raport HTML: {path}", flush=True)
    except Exception as exc:
        warning = f"Nie utworzono raportu HTML: {type(exc).__name__}: {exc}. Wyniki FDTD są zachowane; użyj polecenia report."
        record.manifest.setdefault("warnings", []).append(warning)
        print(warning, file=sys.stderr, flush=True)


def _report(args):
    from antenna_lab.visualization.report import generate_report
    from antenna_lab.visualization.report_data import latest_run
    if bool(args.run_dir) == bool(args.latest):
        raise ConfigurationError("Podaj katalog wyników albo --latest (jedną z tych opcji).")
    run_path = latest_run(args.runs_dir) if args.latest else args.run_dir
    print(f"Odczyt zapisanych wyników: {run_path}", flush=True)
    path = generate_report(run_path, args.output, start_mhz=args.start_mhz,
                           stop_mhz=args.stop_mhz, step_mhz=args.step_mhz)
    print(f"Raport HTML: {path}", flush=True)
    if args.open:
        import webbrowser
        if not webbrowser.open(path.as_uri()):
            print("Przeglądarka nie została otwarta. Otwórz zapisany plik HTML ręcznie.")
    return 0


def main(argv=None):
    arguments = sys.argv[1:] if argv is None else argv
    args = parser().parse_args(arguments or ["preview"])
    try:
        if args.command != "preview":
            import matplotlib
            matplotlib.use("Agg")
        if args.command == "_worker":
            return _worker(args)
        if args.command == "report":
            return _report(args)
        overrides = {}
        for entry in args.set_mm:
            if "=" not in entry:
                raise ConfigurationError("Użyj --set-mm C=75 (wymiar w mm).")
            key, value = entry.split("=", 1)
            overrides[key] = float(value.replace(",", "."))
        config = modified_config(load_config(args.config), overrides, args.frequency_mhz, args.reflector, args.scale_to_mhz)
        if args.command == "preview":
            from antenna_lab.app.editor import show_editor
            show_editor(config, args.output)
        elif args.command == "check":
            from antenna_lab.antennas import build_model
            from antenna_lab.core.geometry import check_geometry
            from antenna_lab.solvers.mesh import make_mesh
            geometry = build_model(config)
            print(json.dumps({"geometry": check_geometry(geometry), "mesh": make_mesh(geometry, config)[1]}, indent=2, ensure_ascii=False))
        elif args.command == "geometry":
            from antenna_lab.app.actions import export_geometry
            print(export_geometry(config, args.output))
        else:
            return _native_job(config, args.output, args.command)
        return 0
    except (ConfigurationError, OSError, ValueError, RuntimeError) as exc:
        print(f"Błąd: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
