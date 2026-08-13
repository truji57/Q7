# Hoja de Ruta — Protocolo unificado `OPEN_LONG` / `OPEN_SHORT`

> Fecha: 13/08/2026 · Estado: **EN IMPLEMENTACIÓN** (backend + frontend + EAs hechos; falta reiniciar backend, compilar EAs en MT5 y test en vivo)

---

## 1. Contexto / Problemas detectados

1. **Bug de dirección (crítico, ya confirmado con evidencia)**
   - El orquestador usaba `self.current_trend` para las señales `ADD_POSITION`, ignorando el `direction` que trae la propia señal.
   - Hoy: último `CYCLE_START` SHORT a las 07:42 → `current_trend = -1` congelado → todas las `ADD_POSITION direction:1` (compra) se convirtieron en `ENTER_SHORT` en NT8.
   - Ya hay un fix en el working tree (sin commit): `_handle_add_position` ahora usa `signal.get("direction", self.current_trend)`. Este fix queda absorbido por el protocolo nuevo (ver §4).

2. **Protocolo fragmentado entre los 2 EAs**
   - `EA_TrendScaling` emite: `CYCLE_START`, `ADD_POSITION`, `CYCLE_END`, `HEARTBEAT`.
   - `Q7_SignalCatcher` emite solo: `CYCLE_START` (uno por ticket nuevo), `HEARTBEAT`.
   - El orquestador tiene 3 handlers distintos (`_handle_cycle_start`, `_handle_cycle_end`, `_handle_add_position`) para algo que debería ser 1.

3. **Instrumento hardcodeado**
   - El orquestador escribe siempre `"MNQ 09-26"` en el comando TRADE.
   - Las señales llegan con `instrument` real (USTEC, NAS100 según broker, etc.).
   - Hay que mapear símbolos MT5/CFD → futuros NT8 (MNQ, MYM, MES, MGC, ...).

4. **Contratos**
   - El `volume` que manda MT5 no se usa para nada en la práctica: el tamaño lo decide el usuario con el parámetro **CT** de cada cuenta.
   - Decisión: los contratos salen SIEMPRE del CT de la cuenta; el `contracts/volume` de la señal se ignora.

5. **Salidas**
   - `CYCLE_END` nunca se ha usado de forma efectiva: las posiciones se cierran solas al alcanzar límites por flotante (TPC/SLC/PDLL/PDPT/TPG/SLG).
   - Decisión: **eliminar** el cierre por `CYCLE_END`. Cierre SOLO por límites de riesgo.

6. **Spam de señales**
   - `EA_TrendScaling` emitió 15 `CYCLE_START` en 30 min por la mañana (tendencia lateral). Hay que garantizar que solo emita `OPEN_*` en eventos reales (cambio de estado/dirección), no en cada re-evaluación.

---

## 2. Decisión de diseño — Protocolo unificado

Los 2 EAs (SignalCatcher y TrendScaling) emiten SOLO estos tipos:

```json
{"type":"OPEN_LONG","instrument":"USTEC","volume":0.10}
{"type":"OPEN_SHORT","instrument":"USTEC","volume":0.10}
{"type":"HEARTBEAT","instrument":"USTEC"}
```

- `type` = `OPEN_LONG` / `OPEN_SHORT` / `HEARTBEAT`. **Nada más.**
- El `volume` es informativo (se ignora en el orquestador; el tamaño lo pone CT).
- Archivos: se mantienen los nombres actuales para no pisarse:
  - Catcher: `Q7\signals\cyclescale_catcher_<N>.json`
  - TrendScaling: `Q7\signals\cyclescale_<N>.json`
  - Heartbeat Catcher: `Q7\signals\heartbeat_catcher.json`

### Regla de oro de la entrada (lo que pide el usuario)
- `OPEN_LONG` → enviar `ENTER_LONG` a la cuenta activa.
  - Si la cuenta ya tiene LONG abierta → **añadir posición** con los contratos CT (NT8 agrega órdenes same-direction).
  - Si tiene SHORT → NT8 cierra+abre (espejo natural).
- `OPEN_SHORT` → simétrico.
- La dirección sale SIEMPRE de la señal. Se elimina `current_trend`.

---

## 3. Cambios en el ORQUESTADOR (`backend/app/engine/orchestrator.py`)

1. **Unificar handlers**: reemplazar `_handle_cycle_start` + `_handle_add_position` + `_handle_cycle_end` por un único `_handle_entry(signal)` para `OPEN_LONG`/`OPEN_SHORT`.
2. **Dirección**: siempre de la señal. **Eliminar `self.current_trend`** (y su uso).
3. **Contratos**: `_write_trade(..., max(1, account.ct), ...)` — ignorar `volume` de la señal.
4. **Instrumento**: consultar el **symbols_map** (ver §5) para traducir `signal.instrument` → instrumento NT8. Si no hay mapeo → usar valor por defecto configurable (actual `MNQ 09-26`) y loguear aviso.
5. **Permitir añadir a la misma cuenta**:
   - Quitar el guard `if account.status == "TRADING": return` (bloquea añadir).
   - Quitar el bloqueo "si hay posición abierta en el grupo" para la MISMA cuenta activa (este bloqueo solo debe aplicar a **rotar/activar OTRA cuenta**).
   - Mantener los guards de rotación ya hechos en `_next_account` y en el reset continuo (no activar otra cuenta mientras haya posiciones abiertas).
6. **Eliminar cierre por CYCLE_END** (borrar `_handle_cycle_end`). El cierre queda exclusivamente por límites en `_sync_balances` (TPC/SLC/PDLL/PDPT/TPG/SLG).
7. **Tolerancia temporal (migración limpia)**: durante la transición, mapear los tipos viejos (`CYCLE_START`, `ADD_POSITION`) al mismo camino de entrada que `OPEN_LONG/OPEN_SHORT`, para que archivos antiguos no se pierdan ni rompan.
8. **HEARTBEAT**: se mantiene (flag de conexión MT5).

---

## 4. Cambios en `Q7_SignalCatcher.mq5`

- `WriteSignal(direction, symbol, volume)` → escribir `type = OPEN_LONG` si `direction==1`, `OPEN_SHORT` si `-1`. Mantener `instrument` y `volume` en el JSON.
- Mantener: detección de tickets nuevos, snapshot inicial, heartbeat cada 30s, filtro de símbolo (`InpSymbolWatch`).
- Desplegar: copiar el `.mq5` al terminal MT5 y compilarlo.

---

## 5. Symbols Map (nuevo — diccionario MT5 → NT8)

**Objetivo**: traducir el símbolo que manda el EA (USTEC, NAS100, US100, ...) al instrumento de futuros en NT8 (MNQ 09-26, MYM, MES, MGC, ...).

### Diseño propuesto
- **Almacenamiento**: nueva tabla SQLite `symbol_maps` (o columna JSON en `config`).
  - `id`, `mt5_symbol` (ej. `USTEC`), `nt8_instrument` (ej. `MNQ 09-26`), `active`.
- **Edición**: nueva sección/menú en el **Settings (ConfigPage)** — tabla editable: símbolo MT5 → instrumento NT8. Botón "añadir fila" / "borrar".
- **API**: endpoints GET/PUT `/api/symbols` (leer/guardar el mapa).
- **Orquestador**: al escribir el trade, `nt8_instrument = symbols_map.get(signal.instrument) or default_instrument`.
- **Defaults sugeridos** (a confirmar):
  - `USTEC` → `MNQ 09-26`
  - `NAS100` → `MNQ 09-26`
  - `US100` → `MNQ 09-26`
  - `MYM` → `MYM 09-26`
  - `MES` → `MES 09-26`
  - `MGC` → `MGC 09-26`
- **Default_instrument** configurable (el `MNQ 09-26` actual) para símbolos no mapeados + log de aviso.

---

## 6. Cambios en `EA_TrendScaling.mq5`

- `PostSignal(...)`: emitir `OPEN_LONG`/`OPEN_SHORT` en lugar de `CYCLE_START`/`ADD_POSITION`.
  - `AbrirPrimeraPosicion(direccion)` → `OPEN_LONG` si `direccion==1`, `OPEN_SHORT` si `-1`.
  - `EvaluarSumaPosicion()` (add) → mismo `OPEN_*` que el ciclo (es una señal de añadir).
  - Eliminar `CYCLE_END`.
  - Mantener `HEARTBEAT`.
- **Guard anti-spam (importante)**: solo emitir `OPEN_*` cuando haya un cambio real de estado (transición espera→ciclo, o cambio de dirección confirmada). No en cada re-evaluación de tendencia. El orquestador añadirá contratos con cada OPEN repetido, así que esto es CRÍTICO para no sobre-dimensionar.
- Desplegar y compilar en el terminal MT5.

---

## 7. Otros ficheros del backend afectados

| Fichero | Cambio |
|---------|--------|
| `backend/app/models/account.py` | (si tabla nueva) modelo `SymbolMap` |
| `backend/app/database.py` | migración: crear tabla `symbol_maps` / columna de default |
| `backend/app/schemas/account.py` | esquema de SymbolMap para la API |
| `backend/app/api/routes.py` | endpoints `/api/symbols` (GET/PUT) |

## 8. Frontend afectado

| Fichero | Cambio |
|---------|--------|
| `frontend/src/pages/ConfigPage.tsx` | nueva sección "Symbols Map" editable |
| `frontend/src/lib/api.ts` | métodos `getSymbols` / `saveSymbols` |
| `frontend/src/types/index.ts` | tipo `SymbolMap` |

---

## 9. Cambios que YA están en el working tree (sin commit) y su destino

- Fix dirección en `_handle_add_position` → **absorbido** por el handler unificado (§3).
- Guards del modo continuo (`_group_has_open_positions`, `_next_account`) → **se mantienen** (protección de rotación).
- ActivityLog persistente (BD + endpoint `/activity` + badges dashboard) → **se mantiene**.
- Se conservan; el commit final incluirá todo.

## 10. Qué NO cambia

- **AddOn NT8** (`Q7AccountManagerAddOn.cs`): sigue siendo puente tonto (TRADE / CLOSE_ALL). No se toca.
- **Comunicación por archivos**: sin cambios.
- **Límites de riesgo** (TPC/SLC/PDLL/PDPT/TPG/SLG): intactos; siguen siendo el mecanismo de cierre.
- **Rotación de cuentas / reset continuo**: intacta (solo se refinan los guards).

## 11. Orden de implementación sugerido

1. [x] **Orquestador**: handler unificado + eliminar `current_trend` + eliminar CYCLE_END + quitar guard de "misma cuenta". *(hecho — `_handle_entry`/`_send_entry`/`_reset_continuo`)*
2. [x] **Symbols Map**: modelo + migración + API + lectura en `_write_trade`. *(hecho — tabla `symbol_maps`, GET/PUT `/api/symbols`)*
3. [x] **Frontend**: sección Symbols Map en Settings. *(hecho — ConfigPage)*
4. [x] **Catcher** (`.mq5`): emitir `OPEN_LONG/OPEN_SHORT`, desplegado en MT5.
5. [x] **TrendScaling** (`.mq5`): emitir `OPEN_LONG/OPEN_SHORT` + guard anti-spam, desplegado en MT5 (backup 023).
6. [ ] **Pruebas en vivo**: reiniciar backend, compilar EAs (F7), validar flujo.

## 12. Pruebas / verificación (antes de cerrar)

- [ ] Reiniciar backend y confirmar Activity Log llenándose.
- [ ] Simular `OPEN_LONG` con LONG abierta → comprobar ENTER_LONG (añade) en NT8.
- [ ] Simular `OPEN_SHORT` con LONG abierta → comprobar cierre+SHORT.
- [ ] Señal con símbolo mapeado (USTEC→MNQ) y sin mapear (default + log).
- [ ] Confirmar que ya no hay cierres por CYCLE_END.
- [ ] Modo continuo: rotación correcta (sin activar otra cuenta con posiciones abiertas).
- [ ] Test flujo completo con el Catcher en cuenta real de broker.
