# OIHK Basic

# ⚠️ SOLO PARA REVISAR EL CÓDIGO — APLICACIÓN NO ESTABLE ⚠️

> **Este repositorio se publica únicamente para que otras personas puedan ver, estudiar y revisar el código fuente de OIHK Basic. La aplicación todavía no está lista para uso normal ni para producción. Puede contener muchos fallos, funciones incompletas, cambios incompatibles y problemas que causen pérdida o corrupción de datos.**
>
> **Actualmente no existe una versión estable ni un instalador oficial recomendado para producción. La única distribución prevista es una candidata alpha experimental (0.1.1-alpha.2), publicada como prerelease de prueba para testers. Los artefactos de GitHub Actions y los binarios alpha no deben considerarse una distribución oficial ni una descarga recomendada para uso real.**
>
> **No uses esta versión como única copia de evidencia, datos importantes o investigaciones reales.**

## Estado del proyecto

OIHK Basic se encuentra en desarrollo activo. Se publica una **candidata alpha experimental (0.1.1-alpha.2)** como prerelease dirigida a testers, además de la vista previa del código fuente.

- No hay una versión estable disponible.
- La única distribución prevista es la candidata alpha experimental; no hay instaladores oficiales.
- GitHub Actions no es un canal público de distribución para usuarios finales.
- La compilación manual está destinada únicamente a desarrollo, revisión técnica y pruebas controladas.
- No se garantiza compatibilidad entre commits, integridad de datos, soporte ni funcionamiento completo.
- Cualquier prueba debe realizarse con datos desechables y backups externos verificados.

Publicar una candidata alpha experimental **no significa que la aplicación esté lanzada ni sea estable**. La alpha está identificada expresamente como tal y se espera que los testers informen de fallos.

## Descripción

OIHK Basic es la edición comunitaria, local-first y monousuario de OIHK. Su objetivo es organizar investigaciones autorizadas, fuentes, evidencia y relaciones utilizando los recursos del computador del usuario, sin requerir obligatoriamente una cuenta, una nube ni un modelo de IA remoto.

Este proyecto vive en su repositorio propio: `Broskigx/OIHK-Basic`. No importa código ni datos de OIHK durante la ejecución y utiliza su propia base SQLite, almacenamiento y configuración.

## Funciones en desarrollo

El código incluye o contempla once áreas principales:

1. Dashboard operativo con investigaciones recientes, cola de revisión, recursos y accesos rápidos.
2. Investigations para crear, editar, duplicar, archivar, restaurar, eliminar, importar y exportar casos.
3. Intelligence Graph con Canvas 2D, selección múltiple, cámara, minimapa, layouts, filtros, pinning, undo/redo y snapshots persistentes.
4. OSINT Workspace con consultas explícitas, historial SQLite, cancelación y promoción controlada al grafo.
5. Evidence Lab con carga por streaming, almacenamiento administrado, SHA-256, verificación, asociaciones, manifiesto y análisis forense.
6. Reports con constructor por secciones, plantillas, historial, Markdown, HTML seguro, JSON y aprobación de borradores.
7. Copilot con conversaciones persistentes y uso de un modelo local configurado por el usuario.
8. Local Models con compatibilidad actual para LM Studio mediante su endpoint local OpenAI-compatible. Otros backends continúan en desarrollo o validación.
9. Data Sources para revisar procedencia, citas y confiabilidad.
10. Settings con apariencia, almacenamiento, privacidad, rendimiento, backups y diagnósticos sanitizados.
11. About con límites, privacidad, versión y alcance de la edición.

Varias de estas funciones pueden estar incompletas, desactivadas, sujetas a rediseño o contener fallos importantes.

## Principios del proyecto

- SQLite y los archivos locales son la fuente de verdad.
- La API debe escuchar únicamente en loopback cuando la autenticación está desactivada.
- No hay telemetría obligatoria, sincronización cloud, licencias, Redis, GraphQL ni infraestructura enterprise.
- Copilot e informes asistidos son opcionales y están diseñados para modelos locales o autoalojados.
- Una consulta OSINT no debe modificar el grafo hasta que el usuario promueva explícitamente el resultado.
- La evidencia no debe ejecutarse; se copia a almacenamiento administrado, se limita por tamaño y se verifica por hash.
- El sistema no debe fabricar resultados, fuentes ni métricas.

## Compilar y ejecutar — solo desarrollo

No existe un instalador estable recomendado. La candidata alpha (prerelease) y la compilación manual están destinadas únicamente a testers y revisión técnica bajo su propia responsabilidad.

Requisitos de desarrollo:

- Python 3.11
- Node.js 22
- Rust estable y Tauri 2 para la aplicación de escritorio

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

La interfaz de desarrollo queda normalmente en `http://127.0.0.1:5173` y la API en `http://127.0.0.1:8000`.

La compilación completa por plataforma se documenta en [docs/BUILDING.md](docs/BUILDING.md). Estas instrucciones no convierten el resultado en una versión estable ni oficialmente soportada.

## Calidad y pruebas

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

Que las pruebas automáticas terminen correctamente no garantiza que la aplicación esté lista para producción, que todas las rutas hayan sido verificadas ni que no existan fallos de seguridad o pérdida de datos.

## Privacidad y modelos locales

Casos, grafo, evidencia administrada, reportes, conversaciones, configuración y backups están diseñados para almacenarse localmente. OIHK Basic no pretende depender obligatoriamente de servicios cloud.

### Compatibilidad actual del Copilot

Por ahora, el backend local compatible y recomendado es **LM Studio**, utilizando su servidor OpenAI-compatible en:

```text
http://127.0.0.1:1234
```

El usuario debe cargar y mantener el modelo dentro de LM Studio. OIHK Basic no incluye pesos de modelos ni descarga modelos automáticamente. La compatibilidad con Ollama y otros endpoints locales o privados puede existir parcialmente en el código, pero continúa en desarrollo y no se garantiza en esta vista previa.

Para obtener mejores resultados en tareas de investigación, planificación y uso de herramientas, se recomienda utilizar, cuando el hardware lo permita:

- modelos locales de tipo **orchestrator**, preparados para coordinar instrucciones, herramientas y flujos de trabajo complejos;
- variantes **abliterated**, cuando el usuario necesite reducir rechazos injustificados en tareas legítimas y autorizadas;
- modelos con buen seguimiento de instrucciones, contexto amplio y capacidad de razonamiento.

Los modelos abliterated no vuelven correctas, legales ni seguras todas sus respuestas. Pueden producir contenido erróneo, inseguro o excesivamente permisivo. Toda salida del Copilot debe ser revisada por una persona antes de utilizarse, incorporarse a un informe o aplicarse sobre una investigación real.

Algunas fuentes externas, como DNS, RDAP/WHOIS, transparencia de certificados, Brave o SearXNG, pueden requerir conexión de red, una clave o un endpoint aportado por el usuario. El repositorio no debe contener credenciales privadas ni claves de proveedores.

## Backups y datos

Las migraciones, backups automáticos y mecanismos de recuperación continúan en desarrollo. No deben considerarse una garantía de integridad.

Para cualquier prueba:

- utiliza datos desechables;
- conserva backups externos;
- verifica que los backups puedan restaurarse;
- no uses OIHK Basic como única copia de evidencia o información importante.

## Distribución y actualizaciones

Los candidatos alpha (0.1.1-alpha.x) se publican como prereleases dentro de **GitHub Releases** con notas de versión y firma del updater, pero **ese canal no está habilitado para usuarios finales** y puede cambiar o retirarse.

No descargues ni redistribuyas binarios como si fueran una versión estable u oficial.

La arquitectura prevista se describe en [docs/UPDATES.md](docs/UPDATES.md) y el proceso futuro de publicación en [docs/RELEASING.md](docs/RELEASING.md).

## Autenticación opcional

Basic está diseñado por defecto como una aplicación monousuario sin login, manteniendo el backend en loopback. Para despliegues personalizados se contempla `OIHK_AUTH_ENABLED=true` junto con protecciones JWT y CSRF. Este modo también debe considerarse experimental mientras no exista una versión estable.

## Diferencia frente a OIHK normal

OIHK Basic busca conservar un flujo profesional local de investigación y un canvas avanzado, pero no incluye colaboración multiusuario, administración de organizaciones, conectores privados, sincronización cloud, facturación, licencias ni infraestructura distribuida.

OIHK normal y OIHK Basic se desarrollan y publican en repositorios separados.

## Uso autorizado

OIHK Basic está destinado al trabajo con fuentes públicas o datos incorporados legalmente por el usuario. No autoriza acceso a sistemas, cuentas o datos privados de terceros.

No incluye como objetivo bypass de CAPTCHA, evasión, acceso autenticado ajeno, enumeración masiva, identificación facial ni recolección de redes no públicas. Las capacidades incompletas y límites conocidos se documentan en [docs/KNOWN_LIMITATIONS.md](docs/KNOWN_LIMITATIONS.md).

## Licencia

MIT. Véase [LICENSE](LICENSE).
