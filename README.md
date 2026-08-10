<div align="center">
  <a href="https://ko-fi.com/broskigx">
    <img src="https://img.shields.io/badge/☕_Apóyame_en_Ko--fi-BROSKIGX-FF5E5B?style=for-the-badge&logo=ko-fi&logoColor=white" alt="Apóyame en Ko-fi — BROSKIGX" />
  </a>
</div>

# OIHK Basic

OIHK Basic es la edición comunitaria, **local-first** y monousuario de OIHK. Está orientada a organizar investigaciones autorizadas, fuentes, evidencia, relaciones y flujos asistidos por modelos locales sin depender obligatoriamente de una cuenta cloud, un servicio remoto o un modelo alojado por terceros.

> [!WARNING]
> **OIHK Basic sigue en fase alpha experimental.** La versión canónica actual es `0.1.1-alpha.2`. No existe una versión estable recomendada para producción y no debe utilizarse como única copia de evidencia, investigaciones o datos importantes.

## Estado del proyecto

- Versión actual: `0.1.1-alpha.2` (`alpha`).
- No hay una release estable disponible.
- Los prereleases alpha están dirigidos a testers y revisión técnica.
- El empaquetado Windows x64/NSIS existe, pero todavía requiere validación de instalación, actualización y desinstalación en entornos limpios antes de considerarse release-ready.
- Linux y macOS tienen soporte de build en desarrollo, pero no se declaran release-ready en esta etapa.
- La compatibilidad entre commits, la integridad de datos y el funcionamiento completo todavía pueden cambiar.

Para cualquier prueba utiliza datos desechables y conserva backups externos verificados.

## Qué es OIHK Basic

OIHK Basic mantiene su propio backend, frontend, base SQLite, almacenamiento y configuración. El objetivo es ofrecer un entorno de investigación local con una superficie de ataque reducida y límites explícitos entre datos, modelos, fuentes externas y módulos especializados.

El proyecto vive en `Broskigx/OIHK-Basic`. No importa código de otros productos OIHK durante la ejecución.

## Capacidades actuales

El código actual incluye, entre otras, estas áreas:

- **Dashboard** con investigaciones recientes, recursos, estado local y accesos rápidos.
- **Investigations / Cases** para crear, editar, archivar, restaurar, importar y exportar casos.
- **Intelligence Graph** con canvas 2D, selección múltiple, layouts, filtros, pinning, undo/redo y snapshots persistentes.
- **OSINT Workspace** con consultas explícitas, historial, cancelación y promoción controlada de resultados al grafo.
- **Evidence management** con almacenamiento administrado, hashing, asociaciones, verificación y una base forense local acotada.
- **Reports** con secciones, plantillas, historial y exportación Markdown, HTML seguro y JSON estructurado.
- **Copilot** con conversaciones persistentes y uso opcional de modelos locales o privados configurados por el usuario.
- **Local Models** con LM Studio como backend actualmente validado.
- **Data Sources** para procedencia, citas y confiabilidad.
- **Settings** para apariencia, almacenamiento, privacidad, rendimiento, backups y diagnósticos sanitizados.
- **OIHK System Link v1** como host/control plane para productos OIHK instalados por separado.

Algunas capacidades continúan en desarrollo o validación. Consulta [Known Limitations](docs/KNOWN_LIMITATIONS.md) para los límites declarados actualmente.

## Evidence Lab no está embebido en Basic

**OIHK Evidence Lab es un producto separado.** Mantiene su propia instalación, proceso, repositorio, UI, dominio y datos especializados.

OIHK Basic actúa como **host/control plane** mediante OIHK System Link v1. No copia el código de Evidence Lab dentro de Basic ni ejecuta código forense recibido arbitrariamente desde un módulo.

La primera integración first-party aprobada es `oihk.evidence-lab`.

### Flujo de System Link v1

1. Basic crea una identidad local Ed25519 y un Link Key temporal de un solo uso.
2. El módulo presenta su identidad, manifest, prueba criptográfica y paquete.
3. Basic verifica compatibilidad, firmas, publisher trust, hashes y límites del paquete.
4. El usuario aprueba únicamente las capacidades solicitadas que desea conceder.
5. Power On verifica nuevamente paquete y ejecutable antes de iniciar el binario registrado.
6. El módulo solo alcanza `READY` después de autenticación mutua firmada y un health check válido.
7. Las rutas y operaciones del módulo quedan limitadas por capabilities y por el estado actual del lifecycle.

### Límites de seguridad de System Link

- Identidades Ed25519 para host, módulo y publisher.
- Link Keys de 128 bits, cinco minutos de vigencia y consumo atómico single-use.
- Publisher trust first-party con trust anchors de release embebidos.
- Publishers de desarrollo desactivados por defecto.
- Verificación SHA-256 del paquete y del ejecutable antes de iniciar el runtime.
- Lifecycle `managed-process` sin shell, scripts ni comandos arbitrarios definidos por el manifest.
- Comunicación posterior mediante requests firmadas con nonce y timestamp.
- Capability gating para APIs del módulo.
- UI del módulo servida desde un paquete verificado dentro de un iframe sandboxed con origen opaco y bridge `postMessage` limitado.
- Reconciliación después de reiniciar Basic mediante identidad, hashes, protocolo, handshake y health firmados; un puerto abierto o PID por sí solo no es suficiente.
- Tres fallos consecutivos del runtime provocan cuarentena; un `READY` sano reinicia el contador de fallos.

El contrato completo está documentado en [docs/SYSTEM_LINK_V1.md](docs/SYSTEM_LINK_V1.md).

## Arquitectura local-first

Principios actuales del proyecto:

- SQLite y los archivos locales son la fuente de verdad de Basic.
- Cuando la autenticación está desactivada, la API debe permanecer en loopback.
- No hay telemetría obligatoria, sincronización cloud, billing, licencias, Redis, GraphQL ni infraestructura distribuida dentro de Basic.
- Copilot y los borradores asistidos son opcionales y dependen de un endpoint configurado por el usuario.
- Las consultas OSINT no deben modificar automáticamente el grafo: los resultados se promueven de forma explícita.
- La evidencia administrada no se ejecuta como parte de la ingestión normal.
- El sistema no debe fabricar fuentes, hallazgos ni métricas cuando una integración no existe o falla.

Algunas fuentes externas requieren red y, según el proveedor, una clave o endpoint aportado por el usuario. DNS, RDAP/WHOIS y certificate transparency son los lookups de red integrados actualmente; otras categorías de inteligencia pueden requerir adaptadores configurados por el usuario.

## Desarrollo local

> Estas instrucciones son para desarrollo, revisión técnica y pruebas controladas. No convierten el build resultante en una versión estable.

### Requisitos

- Python 3.11 o superior.
- Node.js 22 (`>=22 <23`).
- Rust estable y Cargo.
- Tauri 2 y las dependencias nativas de la plataforma.

Consulta [docs/BUILDING.md](docs/BUILDING.md) para los requisitos completos de Windows, Linux y macOS.

### Backend y frontend

```powershell
# Backend
cd backend
python -m pip install -e ".[dev]"
python run.py
```

En otra terminal:

```powershell
cd frontend
npm ci
npm run dev
```

Por defecto, en desarrollo:

- Frontend: `http://127.0.0.1:5173`
- API: `http://127.0.0.1:8000`

## Calidad y pruebas

La CI cubre backend en Windows y Linux, frontend, Rust/Tauri y Gitleaks. Para una revisión local típica:

```powershell
python -m ruff check backend/app backend/run.py scripts tests
python -m pytest -q

cd frontend
npm ci
npm run lint
npm run test -- --run
npm run build
npm audit --audit-level=high

cd ../src-tauri
cargo fmt -- --check
cargo check --locked
cargo test --locked --all-targets
```

System Link incluye además un smoke E2E real entre Basic y un clon local de OIHK Evidence Lab:

```powershell
python scripts/smoke_system_link_e2e.py --evidence-lab C:\path\to\OiHK-evidence-lab
```

El smoke construye el runtime y la UI de Evidence Lab, genera un paquete development firmado y valida el flujo de pairing, aprobación, Power On, autenticación mutua, health `READY`, acceso capability-gated, Power Off, restart, rechazo de replay y rechazo de tampering de paquete/ejecutable.

Que los tests terminen en verde reduce regresiones conocidas, pero no implica que la aplicación sea production-ready ni que todas las rutas posibles hayan sido verificadas.

## Modelos locales y Copilot

OIHK Basic no incluye pesos de modelos ni descarga modelos automáticamente.

El backend actualmente validado para uso local es **LM Studio** mediante su servidor OpenAI-compatible, normalmente en:

```text
http://127.0.0.1:1234
```

El usuario debe cargar y administrar el modelo dentro de LM Studio. Existen rutas de compatibilidad para Ollama y otros endpoints OpenAI-compatible/locales o privados, pero no se garantizan en esta alpha.

Las respuestas de modelos son contenido no verificado. Un modelo no debe aprobar, modificar ni convertir automáticamente información en evidencia confiable sin revisión humana.

## Evidencia, reportes y backups

- La vista previa inline de evidencia se restringe a tipos raster considerados seguros; otros archivos se manejan como attachments.
- Los reportes exportan Markdown, HTML seguro y JSON estructurado. PDF y DOCX no están incluidos actualmente.
- El cambio de directorio de almacenamiento requiere backup y restart; la relocalización en vivo de la base está bloqueada deliberadamente.
- Backups, migraciones y recuperación siguen siendo mecanismos en evolución y no constituyen una garantía absoluta de integridad.

Para pruebas importantes conserva siempre una copia externa y verifica que pueda restaurarse.

## Distribución y actualizaciones

Los builds `0.1.1-alpha.x` son **prereleases experimentales**.

El empaquetado Windows NSIS x64 y el updater firmado existen en el código, pero todavía hay requisitos operacionales antes de una distribución estable: validación en una VM limpia, firma/reputación del ejecutable cuando corresponda y un canal HTTPS apropiado para el updater.

GitHub Actions no debe interpretarse como un canal estable para usuarios finales y los artefactos de CI no deben redistribuirse como releases de producción.

Consulta:

- [docs/BUILDING.md](docs/BUILDING.md)
- [docs/UPDATES.md](docs/UPDATES.md)
- [docs/RELEASING.md](docs/RELEASING.md)

## Autenticación opcional

Basic está pensado por defecto como aplicación monousuario local. Con `OIHK_AUTH_ENABLED=false`, el backend se niega a arrancar en un bind no-loopback.

Para despliegues personalizados existe `OIHK_AUTH_ENABLED=true` con autenticación y protecciones asociadas. Este modo también debe considerarse experimental mientras no exista una versión estable.

## Diferencia frente a OIHK normal

OIHK Basic conserva un flujo local de investigación, evidencia, grafo, modelos y módulos first-party, pero deliberadamente no incluye la infraestructura de una edición multiusuario/enterprise.

Entre los límites de edición actuales están:

- teams y organizations;
- enterprise SSO;
- cloud synchronization;
- private connector administration;
- billing y licensing;
- Redis y queues;
- GraphQL;
- infraestructura distribuida.

OIHK normal y OIHK Basic se desarrollan y publican como productos separados.

## Uso autorizado

OIHK Basic está destinado al trabajo con fuentes públicas, sistemas propios o datos obtenidos e incorporados legalmente por el usuario.

El software no concede autorización para acceder a sistemas, cuentas, redes o información privada de terceros. Las pruebas deben respetar el alcance y permiso aplicable a cada investigación.

## Documentación relevante

- [System Link v1](docs/SYSTEM_LINK_V1.md)
- [Known Limitations](docs/KNOWN_LIMITATIONS.md)
- [Architecture](docs/ARCHITECTURE.md)
- [Building](docs/BUILDING.md)
- [Updates](docs/UPDATES.md)
- [Releasing](docs/RELEASING.md)
- [Threat Model](THREAT_MODEL.md)

## Licencia

MIT. Véase [LICENSE](LICENSE).
