
from pathlib import Path
from threading import Event, Lock
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
import subprocess
import time

# Carpeta donde se encuentra este programa
CARPETA = Path(__file__).resolve().parent
NOTEBOOKS = CARPETA / "Notebooks"

pendiente = Event()
ultimo_cambio = [0.0]
bloqueo = Lock()

def ejecutar(*comando):
    resultado = subprocess.run(
        comando,
        cwd=CARPETA,
        capture_output=True,
        text=True
    )
    if resultado.returncode != 0:
        raise RuntimeError(
            resultado.stderr or resultado.stdout
        )
    return resultado.stdout.strip()

class Detector(FileSystemEventHandler):
    def on_any_event(self, evento):
        if evento.is_directory:
            return

        rutas = [
            getattr(evento, "src_path", ""),
            getattr(evento, "dest_path", "")
        ]

        if any(
            ruta.endswith(".ipynb")
            and ".ipynb_checkpoints" not in Path(ruta).parts
            for ruta in rutas
        ):
            with bloqueo:
                ultimo_cambio[0] = time.monotonic()
                pendiente.set()

def sincronizar():
    ejecutar("git", "add", "-A", "--", "Notebooks")

    cambios = subprocess.run(
        ["git", "diff", "--cached", "--quiet"],
        cwd=CARPETA
    )

    if cambios.returncode == 1:
        ejecutar(
            "git", "commit", "-m",
            "Actualizacion automatica de notebooks"
        )
    elif cambios.returncode != 0:
        raise RuntimeError("Error al revisar cambios de Git")

    ejecutar("git", "push", "origin", "main")
    print("Notebooks sincronizados con GitHub")

if not NOTEBOOKS.is_dir():
    raise SystemExit("No se encontro la carpeta Notebooks")

observador = Observer()
observador.schedule(Detector(), str(NOTEBOOKS), recursive=True)
observador.start()

print("Sincronizacion automatica activada")
print("Vigilando:", NOTEBOOKS)
print("Presiona Ctrl+C para detenerla")

try:
    while True:
        if pendiente.is_set():
            with bloqueo:
                listo = time.monotonic() - ultimo_cambio[0] >= 3

            if listo:
                try:
                    sincronizar()
                    with bloqueo:
                        pendiente.clear()
                except Exception as error:
                    print("Error de sincronizacion:", error)
                    print("Se reintentara en unos segundos")
                    time.sleep(10)

        time.sleep(1)
except KeyboardInterrupt:
    print("Sincronizacion detenida")
finally:
    observador.stop()
    observador.join()
