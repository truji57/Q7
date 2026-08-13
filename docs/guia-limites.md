# Guia de Limites TP/SL - Q7 Trading Engine

## Conceptos Basicos

### Cuenta
Una cuenta es una cuenta de trading en NinjaTrader (ej: Sim101, Sim102...). Cada cuenta tiene su propio balance, posiciones y metricas.

### Grupo
Un grupo es un conjunto de cuentas que se gestionan juntas. El grupo define:
- **Parametros de trading** (CT, MXP, TPC, SLC, TPxR, SLxR, TPG, SLG)
- **Horario de operacion** (schedule)
- **Modo de reinicio** (Manual, Diario, Continuo)
- **Orden de las cuentas** (rotation order)

### Ciclo
Un ciclo es una operacion individual de trading. Cuando el EA de MT5 detecta una senal (LONG o SHORT), el orchestrador abre una posicion en la cuenta activa del grupo. El ciclo termina cuando:
- Se alcanza el **TPC** (Take Profit por Ciclo)
- Se alcanza el **SLC** (Stop Loss por Ciclo)
- La posicion se cierra por otra razon

### Ronda
Una ronda es un conjunto de ciclos. Cuando todas las cuentas del grupo han operado (o han sido deshabilitadas por TPxR/SLxR/TPG/SLG), la ronda termina y comienza una nueva.

---

## Jerarquia de Limites (de menor a mayor)

```
CICLO (TPC/SLC) < RONDA (TPxR/SLxR) < GLOBAL (TPG/SLG)
```

### 1. TPC/SLC - Take Profit / Stop Loss por Ciclo
- **Que es:** El limite de PnL para una operacion individual (un ciclo).
- **Cuando se aplica:** En cada posicion abierta.
- **Que hace:** Cierra la posicion actual cuando se alcanza el limite.
- **Ejemplo:** TPC=$500, SLC=$1000
  - Si el PnL de la posicion alcanza +$500 → se cierra (TPC tocado)
  - Si el PnL de la posicion alcanza -$1000 → se cierra (SLC tocado)
- **Despues de tocar:** La cuenta pasa a la siguiente disponible.

### 2. TPxR/SLxR - Take Profit / Stop Loss por Ronda
- **Que es:** El limite de PnL acumulado para una ronda completa.
- **Cuando se aplica:** Despues de cada cierre de posicion (ciclo).
- **Que hace:** Deshabilita la cuenta (switch OFF) cuando se alcanza el limite.
- **Ejemplo:** TPxR=$1500, SLxR=$2000
  - Si el PNL Ronda de la cuenta alcanza +$1500 → cuenta deshabilitada
  - Si el PNL Ronda de la cuenta alcanza -$2000 → cuenta deshabilitada
- **Despues de tocar:** La cuenta se desactiva y el grupo pasa a la siguiente.

### 3. TPG/SLG - Take Profit / Stop Loss Global
- **Que es:** El limite de PnL total acumulado de la cuenta (desde el inicio).
- **Cuando se aplica:** Despues de cada cierre de posicion (ciclo).
- **Que hace:** Deshabilita la cuenta (switch OFF) cuando se alcanza el limite.
- **Ejemplo:** TPG=$3050, SLG=$2000
  - Si el PNL Total de la cuenta alcanza +$3050 → cuenta deshabilitada
  - Si el PNL Total de la cuenta alcanza -$2000 → cuenta deshabilitada
- **Despues de tocar:** La cuenta se desactiva permanentemente (hasta RESET manual).

---

## Prioridad de Evaluacion

El orchestrador evalua los limites en este orden (de mayor a menor prioridad):

```
1. TPG/SLG (Global) - PRIORIDAD MAXIMA
2. TPxR/SLxR (Ronda)
3. TPC/SLC (Ciclo)
```

**TPG/SLG tiene prioridad sobre TPxR/SLxR.** Si una cuenta alcanza ambos limites (TPG y TPxR), el estado mostrara TPG (no TPxR).

### Flujo de Evaluacion (en cada sync)

```python
# 1. TPG/SLG (Global) - Evalua primero
if total_pnl >= TPG:
    status = "TP_GLOBAL"
    enabled = False
    CLOSE_ALL

if total_pnl <= -SLG:
    status = "SL_GLOBAL"
    enabled = False
    CLOSE_ALL

# 2. TPxR/SLxR (Ronda) - Evalua despues
if round_pnl >= TPxR:
    status = "TP_RONDA"
    CLOSE_ALL

if round_pnl <= -SLxR:
    status = "SL_RONDA"
    CLOSE_ALL

# 3. TPC/SLC (Ciclo) - Evalua al final
if cycle_pnl >= TPC:
    status = "TP_CICLO"
    CLOSE_ALL

if cycle_pnl <= -SLC:
    status = "SL_CICLO"
    CLOSE_ALL
```

---

## Metricas de PnL

### PNL DIA
- **Que es:** El PnL del dia actual (desde medianoche).
- **Fuente:** Directo de NT8 (Gross Realized PnL + Unrealized).
- **Cuando se resetea:** A las 00:00 automaticamente.
- **Uso:** Informativo (no se usa para limites activos).

### PNL RONDA
- **Que es:** El PnL acumulado desde el inicio de la ronda actual.
- **Calculo:** `(realized - round_start_realized) + unrealized`
- **Cuando se resetea:** Al inicio de cada nueva ronda (modo Continuo) o al hacer RESET.
- **Uso:** Se usa para TPxR/SLxR.

### PNL TOTAL
- **Que es:** El PnL total acumulado de la cuenta (desde el inicio).
- **Calculo:** `(balance + unrealized) - starting_balance`
- **Cuando se resetea:** Solo al hacer RESET (cuando se pone INI a 0).
- **Uso:** Se usa para TPG/SLG.

### OPEN
- **Que es:** El PnL flotante de las posiciones abiertas.
- **Fuente:** Unrealized PnL de NT8.
- **Uso:** Informativo.

---

## Modos de Reinicio

### Manual
- Al terminar la ronda (todas las cuentas con TPxR/SLxR/TPG/SLG), el grupo se desactiva.
- Para volver a operar: hacer RESET manual.
- **TP/SL usa:** PNL Ronda.

### Diario
- Al terminar la ronda, el grupo se desactiva.
- A las 00:00, las cuentas se resetean automaticamente.
- **TP/SL usa:** PNL Ronda.

### Continuo
- Al terminar la ronda, el grupo se resetea automaticamente.
- Las cuentas vuelven a PENDING y se inicia una nueva ronda.
- **TP/SL usa:** PNL Ronda.

---

## Boton RESET

Al hacer RESET en un grupo:

1. **Re-habilita** todas las cuentas (enabled = True).
2. **Re-evalua TPG/SLG** con los valores actuales. Deshabilita solo las que hayan alcanzado el limite.
3. **Resetea:** PNL Ronda, OPEN, ronda, posicion, trades.
4. **Empieza** desde la primera cuenta habilitada.
5. **NO toca:** INI, BALANCE, PNL TOTAL, PNL DIA, ni parametros de configuracion (CT-SLG).

---

## Ejemplo Practico

### Configuracion del Grupo
- Cuentas: Sim101, Sim102, Sim103, Sim104, Sim105
- CT: 10 contratos
- TPC: $500 (Take Profit por Ciclo)
- SLC: $1000 (Stop Loss por Ciclo)
- TPxR: $1500 (Take Profit por Ronda)
- SLxR: $2000 (Stop Loss por Ronda)
- TPG: $3050 (Take Profit Global)
- SLG: $2000 (Stop Loss Global)
- Modo: Diario

### Escenario 1: Ciclo normal
1. Sim101 abre LONG con 10 contratos.
2. El PnL de la posicion alcanza +$500.
3. **TPC tocado** → se cierra la posicion.
4. Sim101 pasa a la siguiente cuenta (Sim102).

### Escenario 2: Ronda completada
1. Sim101 ha acumulado +$1500 en PNL Ronda.
2. **TPxR tocado** → Sim101 se desactiva.
3. El grupo pasa a Sim102.

### Escenario 3: Limite Global alcanzado
1. Sim101 ha acumulado +$3050 en PNL Total (desde el inicio).
2. **TPG tocado** → Sim101 se desactiva permanentemente.
3. El grupo pasa a Sim102.

### Escenario 4: RESET
1. El usuario hace RESET en el grupo.
2. Todas las cuentas se re-habilitan.
3. Se re-evalua TPG/SLG: Sim101 tenia TPG=$3050 y PNL Total=$3050 → se desactiva de nuevo.
4. Las demas cuentas quedan habilitadas.
5. Empieza desde Sim102 (primera habilitada).

---

## Parametros de Configuracion

### CT (Contratos)
- **Que es:** Numero de contratos por operacion.
- **Ejemplo:** CT=10 → abre 10 contratos por senal.

### MXP (Maximo de Posiciones)
- **Que es:** Maximo de posiciones simultaneas en un ciclo.
- **Ejemplo:** MXP=6 → no abre mas de 6 posiciones en el mismo ciclo.

### TPC (Take Profit por Ciclo)
- **Que es:** Limite de PnL para cerrar una posicion individual.
- **Ejemplo:** TPC=$500 → cierra cuando el PnL de la posicion alcanza +$500.

### SLC (Stop Loss por Ciclo)
- **Que es:** Limite de PnL para cerrar una posicion individual.
- **Ejemplo:** SLC=$1000 → cierra cuando el PnL de la posicion alcanza -$1000.

### TPxR (Take Profit por Ronda)
- **Que es:** Limite de PnL acumulado para desactivar la cuenta en la ronda.
- **Ejemplo:** TPxR=$1500 → desactiva la cuenta cuando PNL Ronda alcanza +$1500.

### SLxR (Stop Loss por Ronda)
- **Que es:** Limite de PnL acumulado para desactivar la cuenta en la ronda.
- **Ejemplo:** SLxR=$2000 → desactiva la cuenta cuando PNL Ronda alcanza -$2000.

### TPG (Take Profit Global)
- **Que es:** Limite de PnL total acumulado para desactivar la cuenta permanentemente.
- **Ejemplo:** TPG=$3050 → desactiva la cuenta cuando PNL Total alcanza +$3050.

### SLG (Stop Loss Global)
- **Que es:** Limite de PnL total acumulado para desactivar la cuenta permanentemente.
- **Ejemplo:** SLG=$2000 → desactiva la cuenta cuando PNL Total alcanza -$2000.

---

## Prioridades Resumidas

| Limite | Metrica | Alcanzar | Accion |
|--------|---------|----------|--------|
| **TPC/SLC** | PnL del ciclo actual | +TPC o -SLC | Cierra la posicion actual |
| **TPxR/SLxR** | PNL Ronda acumulado | +TPxR o -SLxR | Desactiva la cuenta |
| **TPG/SLG** | PNL Total acumulado | +TPG o -SLG | Desactiva la cuenta permanentemente |

**TPG/SLG > TPxR/SLxR > TPC/SLC**

---

## Notas Importantes

1. **INI (Capital Inicial):** Se configura manualmente en la tabla del dashboard. Es el balance inicial de la cuenta. Se usa para calcular PNL Total.

2. **PNL DIA:** Se calcula directamente desde NT8. No se usa para limites activos, solo es informativo.

3. **Modo Continuo:** Al terminar la ronda, el grupo se resetea automaticamente y empieza una nueva ronda. No requiere intervencion manual.

4. **Modo Manual:** Al terminar la ronda, el grupo se desactiva. Requiere RESET manual para volver a operar.

5. **Modo Diario:** Al terminar la ronda, el grupo se desactiva. A las 00:00 se resetean las cuentas automaticamente.

6. **RESET:** Re-habilita todas las cuentas, re-evalua TPG/SLG, y empieza desde la primera cuenta habilitada. NO toca INI, BALANCE, PNL TOTAL, PNL DIA, ni parametros de configuracion.
