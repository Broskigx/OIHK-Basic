# ⚠️ NOT ESTABLE — ALPHA PÚBLICA ⚠️

> **Esta versión está en desarrollo activo y puede contener errores graves, perder datos o cambiar sin compatibilidad. No la uses como única copia de evidencia. Mantén backups externos verificados y úsala solamente en investigaciones autorizadas.**

# OIHK Basic

OIHK Basic es la edición comunitaria, local-first y monousuario de OIHK. Organiza investigaciones autorizadas, fuentes, evidencia y relaciones sin requerir una cuenta, una nube ni un modelo de IA.

> **Alpha:** esta versión es un candidato previo a publicación y puede contener errores. Mantén backups externos verificados y no la uses como única copia de evidencia. El usuario es responsable de contar con autorización y base legal; OIHK Basic no autoriza acceso a sistemas, cuentas o datos no públicos.

Este proyecto vive en su repositorio propio: `Broskigx/OIHK-Basic`. No importa código ni datos de OIHK durante la ejecución y utiliza su propia base SQLite, almacenamiento, configuración e instaladores.

## Producto

La aplicación incluye once áreas principales:

1. Dashboard operativo con investigaciones recientes, cola de revisión, recursos y accesos rápidos.
2. Investigations con crear, editar, duplicar, archivar, restaurar, eliminar, importar y exportar.
3. Intelligence Graph con Canvas 2D, selección múltiple, cámara, minimapa, layouts, filtros, pinning, undo/redo y snapshots persistentes.
4. OSINT Workspace con consultas explícitas, historial SQLite, cancelación y promoción controlada al grafo.
5. Evidence Lab con carga por streaming, almacenamiento administrado, SHA-256, verificación, asociaciones, manifiesto y análisis forense.
6. Reports con constructor por secciones, plantillas, historial, Markdown, HTML seguro, JSON y aprobación de borradores.
7. Copilot con conversaciones persistentes y uso exclusivo de un modelo local configurado por el usuario.
8. Local Models para detectar y configurar LM Studio, Ollama o un endpoint compatible en una red privada.
9. Data Sources para revisar y mantener procedencia, citas y confiabilidad.
10. Settings con apariencia, almacenamiento, privacidad, rendimiento, backups y diagnósticos sanitizados.
11. About con límites, privacidad, versión y alcance de la edición.

También incluye gestión de entidades y relaciones, timeline, cadena de custodia, transforms deterministas, análisis de hashes, MIME, metadatos e indicadores, importación CSV/GraphML y exportación de investigaciones versionada.

## Principios

- SQLite y archivos locales son la fuente de verdad.
- La API escucha únicamente en loopback cuando la autenticación está desactivada.
- No hay telemetría, sincronización cloud, licencias, Redis, GraphQL ni infraestructura enterprise.
- Copilot e informes asistidos son opcionales y nunca usan un proveedor cloud: aceptan solo endpoints loopback, privados o link-local.
- Una consulta OSINT no modifica el grafo hasta que el usuario promueve el resultado.
- La evidencia nunca se ejecuta; se copia a almacenamiento administrado, se limita por tamaño y se verifica por hash.
- No se fabrican resultados, fuentes ni métricas.

## Instalación de escritorio

El instalador Windows incorpora la interfaz Tauri y el backend FastAPI compilado. No requiere Python ni Node.js en el equipo de destino.

```text
dist/windows/OIHK Basic_0.1.1-alpha.1_x64-setup.exe
```

En el primer inicio se abre un onboarding de ocho pasos. El modelo local es opcional y se puede omitir. Los datos se guardan, por defecto, en:

- Windows: `%APPDATA%/OIHK-Basic/`
- macOS: `~/Library/Application Support/OIHK-Basic/`
- Linux: `$XDG_DATA_HOME/OIHK-Basic/` o `~/.local/share/OIHK-Basic/`

Los secretos de firma y autenticación opcional se generan de forma atómica en el directorio de configuración del sistema operativo.

Requisitos mínimos del candidato Windows x64:

- Windows 10 versión 1809 o posterior, o Windows 11, en arquitectura x64;
- WebView2 Runtime (Windows 11 lo incluye; el instalador puede obtenerlo en Windows 10);
- 4 GB de RAM y 1 GB libre para aplicación y trabajo inicial; evidencia y backups requieren espacio adicional;
- conexión de red solo para consultas OSINT, modelos remotos privados o actualizaciones que el usuario inicie.

La versión empaquetada incluye el frontend, el shell Tauri, el backend FastAPI y SQLite. No incluye pesos de modelos, Ollama, LM Studio, claves de proveedores ni servicios cloud.

## Privacidad, modelos y proveedores

Casos, grafo, evidencia administrada, reportes, conversaciones, configuración y backups se almacenan localmente. OIHK Basic no implementa telemetría. Las conexiones externas ocurren únicamente por acciones explícitas del usuario, comprobación de actualizaciones o servicios que configure.

En **Local Models** se puede detectar Ollama (`http://127.0.0.1:11434`) o LM Studio (`http://127.0.0.1:1234`), elegir un modelo y probarlo. También se acepta un endpoint OpenAI-compatible en localhost o una red privada bajo control del usuario. Copilot es opcional y su salida debe revisarse: no aprueba ni modifica evidencia automáticamente.

DNS, RDAP/WHOIS y transparencia de certificados funcionan sin una cuenta propia cuando el servicio público responde. Brave, SearXNG y otros adaptadores opcionales requieren una clave o endpoint aportado por el usuario mediante Settings o las variables documentadas en [.env.example](.env.example); el instalador no contiene credenciales.

## Backups y desinstalación

Los backups previos a migraciones y actualizaciones son controles de recuperación, no sustituyen una estrategia del usuario. Conserva copias externas cifradas y prueba su restauración. La desinstalación preserva `%APPDATA%\OIHK-Basic`; para borrar esos datos hay que hacerlo de forma separada y consciente después de verificar los backups.

## Actualizaciones seguras

La aplicación de escritorio comprueba por defecto si hay una actualización, pero no descarga ni instala silenciosamente. Settings y About muestran canal, notas, progreso y las decisiones explícitas de descargar y reiniciar. El canal no es utilizable públicamente mientras los artefactos sigan alojados en un repositorio privado.

Cada actualización exige una firma del updater de Tauri y, antes de cerrar el sidecar, crea un backup SQLite consistente y verificado bajo `%APPDATA%\OIHK-Basic\backups\pre-update\`. La desinstalación y la actualización no eliminan la base, evidencia, configuración, historial ni backups.

La arquitectura y recuperación están en [docs/UPDATES.md](docs/UPDATES.md); la publicación de candidatos, en [docs/RELEASING.md](docs/RELEASING.md). El workflow de un tag válido deja un draft prerelease para validación manual; nunca lo publica.

## Desarrollo

Requisitos: Python 3.11, Node.js 22 y, para escritorio, Rust estable/Tauri 2.

```powershell
# Backend
cd backend
python -m pip install -e ".[dev]"
python run.py

# Frontend, en otra terminal
cd frontend
npm ci
npm run dev
```

La interfaz queda en `http://127.0.0.1:5173` y la API, por defecto, en `http://127.0.0.1:8000`.

## Calidad

```powershell
python -m ruff check backend/app backend/run.py scripts tests
python -m pytest -q

cd frontend
npm run lint
npm run test -- --run
npm run build

cd ../src-tauri
cargo fmt -- --check
cargo check --locked
cargo test --locked --all-targets
```

La compilación completa por plataforma se explica en [docs/BUILDING.md](docs/BUILDING.md). La arquitectura y el modelo de seguridad están en [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) y [SECURITY.md](SECURITY.md).

## Autenticación opcional

Basic funciona por defecto como aplicación monousuario sin login y obliga al backend a permanecer en loopback. Para un despliegue personalizado se puede activar `OIHK_AUTH_ENABLED=true`, configurar un administrador y conservar las protecciones JWT/CSRF. El modo `production` rechaza el arranque sin autenticación o con secretos inseguros.

## Diferencia frente a OIHK normal

OIHK Basic conserva el flujo profesional local de investigación y el canvas premium, pero no incluye colaboración multiusuario, administración de organizaciones, conectores privados, sincronización cloud, facturación, licencias ni infraestructura distribuida. OIHK normal y OIHK Basic se desarrollan y publican en repositorios separados.

## Licencia

MIT. Véase [LICENSE](LICENSE).

## Limitaciones y uso autorizado

OIHK Basic trabaja con fuentes públicas o datos incorporados legalmente por el usuario. No incluye bypass de CAPTCHA, evasión, acceso autenticado ajeno, enumeración masiva, identificación facial ni recolección de redes no públicas. Las capacidades incompletas y límites de distribución se mantienen en [docs/KNOWN_LIMITATIONS.md](docs/KNOWN_LIMITATIONS.md).
